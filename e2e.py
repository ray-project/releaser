import argparse
import boto3
import collections
import copy
import datetime
import hashlib
import jinja2
import json
import logging
import multiprocessing
import os
import shutil
import sys
import tempfile
import time
from queue import Empty
from typing import Any, Dict, Optional, Tuple

import yaml

import anyscale
from anyscale.api import instantiate_api_client
from anyscale.controllers.session_controller import SessionController
from anyscale.sdk.anyscale_client.sdk import AnyscaleSDK


logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    fmt="[%(levelname)s %(asctime)s] " "%(filename)s: %(lineno)d  " "%(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


GLOBAL_CONFIG = {
    "ANYSCALE_HOST": os.environ.get("ANYSCALE_HOST", "https://beta.anyscale.com"),
    "ANYSCALE_CLI_TOKEN": os.environ.get("ANYSCALE_CLI_TOKEN"),
    "ANYSCALE_CLOUD_ID": os.environ.get(
        "ANYSCALE_CLOUD_ID", "cld_4F7k8814aZzGG8TNUGPKnc"
    ),  # cld_4F7k8814aZzGG8TNUGPKnc
    "ANYSCALE_PROJECT": os.environ.get(
        "ANYSCALE_PROJECT", "prj_3dcxfLlSDL6HTav8k4NbTb"
    ),  # kf-dev
    "RELEASE_AWS_BUCKET": os.environ.get(
        "RELEASE_AWS_BUCKET", "ray-release-automation-results"
    ),
    "RELEASE_AWS_LOCATION": os.environ.get("RELEASE_AWS_LOCATION", "dev"),
    "RELEASE_AWS_DB_NAME": os.environ.get("RELEASE_AWS_DB_NAME", "ray_ci"),
    "RELEASE_AWS_DB_TABLE": os.environ.get(
        "RELEASE_AWS_DB_TABLE", "release_test_result"
    ),
    "RELEASE_AWS_DB_SECRET_ARN": os.environ.get(
        "RELEASE_AWS_DB_SECRET_ARN",
        "arn:aws:secretsmanager:us-west-2:029272617770:secret:rds-db-credentials/cluster-7RB7EYTTBK2EUC3MMTONYRBJLE/ray_ci-MQN2hh",
    ),
    "RELEASE_AWS_DB_RESOURCE_ARN": os.environ.get(
        "RELEASE_AWS_DB_RESOURCE_ARN",
        "arn:aws:rds:us-west-2:029272617770:cluster:ci-reporting",
    ),
}

REPORT_S = 30

if GLOBAL_CONFIG["ANYSCALE_CLI_TOKEN"] is None:
    print("Missing ANYSCALE_CLI_TOKEN, retrieving from AWS secrets store")
    # NOTE(simon) This should automatically retrieve release-automation@anyscale.com's anyscale token
    GLOBAL_CONFIG["ANYSCALE_CLI_TOKEN"] = boto3.client(
        "secretsmanager", region_name="us-west-2"
    ).get_secret_value(
        SecretId="arn:aws:secretsmanager:us-west-2:029272617770:secret:release-automation/anyscale-token20210505220406333800000001-BcUuKB"
    )[
        "SecretString"
    ]


class State:
    def __init__(self, state: str, timestamp: float, data: Any):
        self.state = state
        self.timestamp = timestamp
        self.data = data


sys.path.insert(0, anyscale.ANYSCALE_RAY_DIR)


def _check_stop(stop_event: multiprocessing.Event):
    if stop_event.is_set():
        raise RuntimeError("Process timed out.")


def _deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = _deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def _dict_hash(dt: Dict[Any, Any]) -> str:
    json_str = json.dumps(dt, sort_keys=True, ensure_ascii=True)
    sha = hashlib.sha256()
    sha.update(json_str.encode())
    return sha.hexdigest()


def _load_config(local_dir: str, config_file: Optional[str]) -> Optional[Dict]:
    if not config_file:
        return None

    config_path = os.path.join(local_dir, config_file)
    with open(config_path, "rt") as f:
        # Todo: jinja2 render
        content = f.read()

    env = copy.deepcopy(os.environ)
    env.update(GLOBAL_CONFIG)

    content = jinja2.Template(content).render(env=env)
    return yaml.safe_load(content)


def has_errored(result: Dict[Any, Any]) -> bool:
    return result.get("status", "invalid") != "finished"


def report_result(
    test_name: str,
    status: str,
    logs: str,
    results: Dict[Any, Any],
    artifacts: Dict[Any, Any],
):
    now = datetime.datetime.utcnow()
    rds_data_client = boto3.client("rds-data", region_name="us-west-2")

    schema = GLOBAL_CONFIG["RELEASE_AWS_DB_TABLE"]

    sql = (
        f"INSERT INTO {schema} "
        f"(created_on, test_name, status, last_logs, results, artifacts) "
        f"VALUES (:created_on, :test_name, :status, :last_logs, :results, :artifacts)"
    )

    rds_data_client.execute_statement(
        database=GLOBAL_CONFIG["RELEASE_AWS_DB_NAME"],
        parameters=[
            {
                "name": "created_on",
                "typeHint": "TIMESTAMP",
                "value": {"stringValue": now.strftime("%Y-%m-%d %H:%M:%S")},
            },
            {"name": "test_name", "value": {"stringValue": test_name}},
            {"name": "status", "value": {"stringValue": status}},
            {"name": "last_logs", "value": {"stringValue": logs}},
            {
                "name": "results",
                "typeHint": "JSON",
                "value": {"stringValue": json.dumps(results)},
            },
            {
                "name": "artifacts",
                "typeHint": "JSON",
                "value": {"stringValue": json.dumps(artifacts)},
            },
        ],
        secretArn=GLOBAL_CONFIG["RELEASE_AWS_DB_SECRET_ARN"],
        resourceArn=GLOBAL_CONFIG["RELEASE_AWS_DB_RESOURCE_ARN"],
        schema=schema,
        sql=sql,
    )


def notify(owner: Dict[Any, Any], result: Dict[Any, Any]):
    logger.error(f"I would now inform {owner['slack']} about this result: " f"{result}")
    # Todo: Send to slack?


def _cleanup_session(sdk: AnyscaleSDK, session_id: str):
    if session_id:
        # Just trigger a request. No need to wait until session shutdown.
        sdk.stop_session(session_id=session_id, stop_session_options={})


def search_running_session(
    sdk: AnyscaleSDK, project_id: str, session_name: str
) -> Optional[str]:
    session_id = None

    logger.info(f"Looking for existing session with name {session_name}")

    result = sdk.search_sessions(
        project_id=project_id, sessions_query=dict(name=dict(equals=session_name))
    )

    if len(result.results) > 0 and result.results[0].state == "Running":
        logger.info("Found existing session.")
        session_id = result.results[0].id
    return session_id


def create_or_find_compute_template(
    sdk: AnyscaleSDK, project_id: str, compute_tpl: Dict[Any, Any]
) -> Optional[str]:
    compute_tpl_id = None
    if compute_tpl:
        compute_tpl_hash = _dict_hash(compute_tpl)

        logger.info(
            f"Tests uses compute template "
            f"with hash {compute_tpl_hash}. Looking up existing "
            f"templates."
        )

        result = sdk.search_compute_templates(dict(project_id=project_id))
        for res in result.results:
            if res.name == compute_tpl_hash:
                compute_tpl_id = res.id
                logger.info(f"Template already exists with ID {compute_tpl_id}")
                break

        if not compute_tpl_id:
            result = sdk.create_compute_template(
                dict(name=compute_tpl_hash, project_id=project_id, config=compute_tpl)
            )
            compute_tpl_id = result.result.id
            logger.info(f"Template created with ID {compute_tpl_id}")

    return compute_tpl_id


def create_or_find_app_config(
    sdk: AnyscaleSDK, project_id: str, app_config: Dict[Any, Any]
) -> Optional[str]:
    app_config_id = None
    if app_config:
        app_config_hash = _dict_hash(app_config)

        logger.info(
            f"Tests uses app config "
            f"with hash {app_config_hash}. Looking up existing "
            f"app configs."
        )

        result = sdk.list_app_configs(project_id=project_id, count=50)
        for res in result.results:
            if res.name == app_config_hash:
                app_config_id = res.id
                logger.info(f"App config already exists with ID {app_config_id}")
                break

        if not app_config_id:
            result = sdk.create_app_config(
                dict(
                    name=app_config_hash, project_id=project_id, config_json=app_config
                )
            )
            app_config_id = result.result.id
            logger.info(f"App config created with ID {app_config_id}")

    return app_config_id


def wait_for_build_or_raise(
    sdk: AnyscaleSDK, app_config_id: Optional[str]
) -> Optional[str]:
    if not app_config_id:
        return None

    # Fetch build
    build_id = None
    result = sdk.list_builds(app_config_id)
    for build in sorted(result.results, key=lambda b: b.created_at):
        build_id = build.id

        if build.status == "failed":
            raise RuntimeError("App config build failed.")

        if build.status == "succeeded":
            return build_id

    if not build_id:
        raise RuntimeError("No build found for app config.")

    # Build found but not failed/finished yet
    completed = False
    start_wait = time.time()
    next_report = start_wait + REPORT_S
    logger.info(f"Waiting for build {build_id} to finish...")
    while not completed:
        now = time.time()
        if now > next_report:
            logger.info(
                f"... still waiting for build {build_id} to finish "
                f"({int(now - start_wait)} seconds) ..."
            )
            next_report = next_report + REPORT_S

        result = sdk.get_build(build_id)
        build = result.result

        if build.status == "failed":
            raise RuntimeError("App config build failed.")

        if build.status == "succeeded":
            return build_id

        completed = build.status not in ["in_progress", "pending"]

        if completed:
            raise RuntimeError(f"Unknown build status: {build.status}")

        time.sleep(1)

    return build_id


def create_and_wait_for_session(
    sdk: AnyscaleSDK,
    stop_event: multiprocessing.Event,
    session_name: str,
    session_options: Dict[Any, Any],
) -> str:

    # Create session
    logger.info(f"Creating session {session_name}")
    result = sdk.create_session(session_options)
    session_id = result.result.id

    # Trigger session start
    logger.info(f"Starting session {session_name} ({session_id})")
    result = sdk.start_session(session_id, start_session_options={})
    sop_id = result.result.id
    completed = result.result.completed

    # Wait for session
    logger.info(f"Waiting for session {session_name}...")
    start_wait = time.time()
    next_report = start_wait + REPORT_S
    while not completed:
        _check_stop(stop_event)
        now = time.time()
        if now > next_report:
            logger.info(
                f"... still waiting for session {session_name} "
                f"({int(now - start_wait)} seconds) ..."
            )
            next_report = next_report + REPORT_S

        session_operation_response = sdk.get_session_operation(
            sop_id, _request_timeout=30
        )
        session_operation = session_operation_response.result
        completed = session_operation.completed
        time.sleep(1)

    return session_id


def run_session_command(
        sdk: AnyscaleSDK,
        session_id: str,
        cmd_to_run: str,
        stop_event: multiprocessing.Event,
        result_queue: multiprocessing.Queue,
        env_vars: Dict[str, str],
        state_str: str = "CMD_RUN"
) -> Tuple[str, int]:
    full_cmd = " ".join(
        f"{k}={v}" for k, v in env_vars.items()) + " " + cmd_to_run

    logger.info(
        f"Running command in session {session_id}: \n" f"{full_cmd}"
    )
    result_queue.put(State(state_str, time.time(), None))
    result = sdk.create_session_command(
        dict(session_id=session_id, shell_command=full_cmd)
    )

    scd_id = result.result.id
    completed = result.result.finished_at is not None

    start_wait = time.time()
    next_report = start_wait + REPORT_S
    while not completed:
        _check_stop(stop_event)

        now = time.time()
        if now > next_report:
            logger.info(
                f"... still waiting for command to finish "
                f"({int(now - start_wait)} seconds) ..."
            )
            next_report = next_report + REPORT_S

        result = sdk.get_session_command(session_command_id=scd_id)
        completed = result.result.finished_at
        time.sleep(1)

    status_code = result.result.status_code

    if status_code != 0:
        raise RuntimeError(
            f"Command returned non-success status: {status_code}"
        )

    return scd_id, status_code


def get_command_logs(
    session_controller: SessionController, scd_id: str, lines: int = 50
):
    result = session_controller.api_client.get_execution_logs_api_v2_session_commands_session_command_id_execution_logs_get(
        session_command_id=scd_id, start_line=-1 * lines, end_line=0
    )

    return result.result.lines


def get_remote_json_content(
    temp_dir: str,
    session_name: str,
    remote_file: Optional[str],
    session_controller: SessionController,
):
    if not remote_file:
        logger.warning("No remote file specified, returning empty dict")
        return {}
    local_target_file = os.path.join(temp_dir, ".tmp.json")
    session_controller.pull(
        session_name=session_name, source=remote_file, target=local_target_file
    )
    with open(local_target_file, "rt") as f:
        return json.load(f)


def pull_artifacts_and_store_in_cloud(
    temp_dir: str,
    logs: str,
    session_name: str,
    test_name: str,
    artifacts: Optional[Dict[Any, Any]],
    session_controller: SessionController,
):
    output_log_file = os.path.join(temp_dir, "output.log")
    with open(output_log_file, "wt") as f:
        f.write(logs)

    bucket = GLOBAL_CONFIG["RELEASE_AWS_BUCKET"]
    location = f"{GLOBAL_CONFIG['RELEASE_AWS_LOCATION']}" f"/{session_name}/{test_name}"
    saved_artifacts = {}

    s3_client = boto3.client("s3")
    s3_client.upload_file(output_log_file, bucket, f"{location}/output.log")
    saved_artifacts["output.log"] = f"s3://{bucket}/{location}/output.log"

    # Download artifacts
    if artifacts:
        for name, remote_file in artifacts.items():
            logger.info(f"Downloading artifact `{name}` from " f"{remote_file}")
            local_target_file = os.path.join(temp_dir, name)
            session_controller.pull(
                session_name=session_name, source=remote_file, target=local_target_file
            )

            # Upload artifacts to s3
            s3_client.upload_file(local_target_file, bucket, f"{location}/{name}")
            saved_artifacts[name] = f"s3://{bucket}/{location}/{name}"

    return saved_artifacts


def run_test_config(
    local_dir: str,
    project_id: str,
    test_name: str,
    test_config: Dict[Any, Any],
    smoke_test: bool = False,
) -> Dict[Any, Any]:
    """

    Returns:
        Dict with the following entries:
            status (str): One of [finished, error, timeout]
            command_link (str): Link to command (Anyscale web UI)
            last_logs (str): Last logs (excerpt) to send to owner
            artifacts (dict): Dict of artifacts
                Key: Name
                Value: S3 URL
    """
    # Todo (mid-term): Support other cluster definitions (not only cluster configs)
    cluster_config_rel_path = test_config["cluster"].get("cluster_config", None)
    cluster_config = _load_config(local_dir, cluster_config_rel_path)

    app_config_rel_path = test_config["cluster"].get("app_config", None)
    app_config = _load_config(local_dir, app_config_rel_path)

    compute_tpl_rel_path = test_config["cluster"].get("compute_template", None)
    compute_tpl = _load_config(local_dir, compute_tpl_rel_path)

    stop_event = multiprocessing.Event()
    result_queue = multiprocessing.Queue()

    session_name = f"{test_name}_{int(time.time())}"

    temp_dir = tempfile.mkdtemp()

    def _run(logger):
        # Unfortunately, there currently seems to be no great way to
        # transfer files with the Anyscale SDK.
        # So we use the session controller instead.
        with open(os.path.join(local_dir, ".anyscale.yaml"), "wt") as f:
            f.write(f"project_id: {project_id}")
        os.chdir(local_dir)

        # Setup interface
        sdk = AnyscaleSDK(auth_token=GLOBAL_CONFIG["ANYSCALE_CLI_TOKEN"])
        session_controller = SessionController(
            api_client=instantiate_api_client(
                cli_token=GLOBAL_CONFIG["ANYSCALE_CLI_TOKEN"],
                host=GLOBAL_CONFIG["ANYSCALE_HOST"],
            ),
            anyscale_api_client=sdk.api_client,
        )
        session_id = None
        scd_id = None

        try:
            # First, look for running sessions
            session_id = search_running_session(sdk, project_id, session_name)
            if not session_id:
                logger.info("No session found.")
                # Start session
                session_options = dict(name=session_name, project_id=project_id)

                if cluster_config is not None:
                    logging.info("Starting session with cluster config")
                    cluster_config_str = json.dumps(cluster_config)
                    session_options["cluster_config"] = cluster_config_str
                    session_options["cloud_id"] = (GLOBAL_CONFIG["ANYSCALE_CLOUD_ID"],)
                    session_options["uses_app_config"] = False
                else:
                    logging.info("Starting session with app/compute config")

                    # Find/create compute template
                    compute_tpl_id = create_or_find_compute_template(
                        sdk, project_id, compute_tpl
                    )

                    # Find/create app config
                    app_config_id = create_or_find_app_config(
                        sdk, project_id, app_config
                    )
                    build_id = wait_for_build_or_raise(sdk, app_config_id)

                    session_options["compute_template_id"] = compute_tpl_id
                    session_options["build_id"] = build_id
                    session_options["uses_app_config"] = True

                session_id = create_and_wait_for_session(
                    sdk=sdk,
                    stop_event=stop_event,
                    session_name=session_name,
                    session_options=session_options,
                )

            # Rsync up
            logger.info("Syncing files to session...")
            session_controller.push(
                session_name=session_name,
                source=None,
                target=None,
                config=None,
                all_nodes=False,
            )

            _check_stop(stop_event)

            results_json = test_config["run"].get("results", None)
            if results_json is None:
                results_json = "/tmp/release_test_out.json"

            env_vars = {
                "RAY_ADDRESS": os.environ.get("RAY_ADDRESS", "auto"),
                "TEST_OUTPUT_JSON": results_json,
                "IS_SMOKE_TEST": "1" if smoke_test else "0",
            }

            # Optionally run preparation command
            prepare_command = test_config["run"].get("prepare")
            if prepare_command:
                logger.info(
                    f"Running preparation command: {prepare_command}"
                )
                run_session_command(
                    sdk=sdk,
                    session_id=session_id,
                    cmd_to_run=prepare_command,
                    stop_event=stop_event,
                    result_queue=result_queue,
                    env_vars=env_vars,
                    state_str="CMD_PREPARE"
                )

            # Run release test command
            cmd_to_run = test_config["run"]["script"] + " "

            args = test_config["run"].get("args", [])
            if args:
                cmd_to_run += " ".join(args) + " "

            if smoke_test:
                cmd_to_run += " --smoke-test"

            scd_id, status_code = run_session_command(
                sdk=sdk,
                session_id=session_id,
                cmd_to_run=cmd_to_run,
                stop_event=stop_event,
                result_queue=result_queue,
                env_vars=env_vars,
                state_str="CMD_RUN"
            )

            logger.info(f"Command finished successfully.")
            if results_json:
                results = get_remote_json_content(
                    temp_dir=temp_dir,
                    session_name=session_name,
                    remote_file=results_json,
                    session_controller=session_controller,
                )
            else:
                results = {
                    "passed": 1
                }

            logs = get_command_logs(
                session_controller, scd_id, test_config.get("log_lines", 50)
            )

            saved_artifacts = pull_artifacts_and_store_in_cloud(
                temp_dir=temp_dir,
                logs=logs,  # Also save logs in cloud
                session_name=session_name,
                test_name=test_name,
                artifacts=test_config.get("artifacts", {}),
                session_controller=session_controller,
            )

            logger.info("Fetched results and stored on the cloud. Returning.")

            result_queue.put(
                State(
                    "END",
                    time.time(),
                    {
                        "status": "finished",
                        "last_logs": logs,
                        "results": results,
                        "artifacts": saved_artifacts,
                    },
                )
            )

        except Exception as e:
            logger.error(e, exc_info=True)

            logs = str(e)
            if scd_id is not None:
                try:
                    logs = get_command_logs(
                        session_controller, scd_id, test_config.get("log_lines", 50)
                    )
                except Exception as e2:
                    logger.error(e2, exc_info=True)

            result_queue.put(
                State("END", time.time(), {"status": "error", "last_logs": logs})
            )
        finally:
            _cleanup_session(sdk, session_id)
            shutil.rmtree(temp_dir)

    timeout = test_config["run"].get("timeout", 1800)

    process = multiprocessing.Process(target=_run, args=(logger,))

    logger.info(f"Starting process with timeout {timeout}")
    process.start()

    # This is a timeout for the full run
    # Should we add a specific build timeout here?
    timeout_time = time.time() + timeout

    result = {}
    while process.is_alive():
        try:
            state: State = result_queue.get(timeout=1)
        except (Empty, TimeoutError):
            if time.time() > timeout_time:
                stop_event.set()
                logger.warning("Process timed out")
                time.sleep(10)
                process.terminate()
                logger.warning("Terminating process")
                break
            continue

        if not isinstance(state, State):
            raise RuntimeError(f"Expected `State` object, got {result}")

        if state.state == "CMD_RUN":
            # Reset timeout after build finished
            timeout_time = state.timestamp + timeout

        elif state.state == "END":
            result = state.data
            break

    while not result_queue.empty():
        state = result_queue.get_nowait()
        result = state.data

    logger.info("Final check if everything worked.")
    try:
        result.setdefault("status", "error")
    except (TimeoutError, Empty):
        result = {"status": "timeout", "last_logs": "Test timed out."}

    logger.info(f"Final results: {result}")

    return result


def run_test(
    test_config_file: str, test_name: str, project_id: str, smoke_test: bool = False
):
    with open(test_config_file, "rt") as f:
        test_configs = yaml.load(f, Loader=yaml.FullLoader)

    test_config_dict = {}
    for test_config in test_configs:
        name = test_config.pop("name")
        test_config_dict[name] = test_config

    if test_name not in test_config_dict:
        raise ValueError(
            f"Test with name `{test_name}` not found in test config file "
            f"at `{test_config_file}`."
        )

    test_config = test_config_dict[test_name]

    if smoke_test and "smoke_test" in test_config:
        smoke_test_config = test_config.pop("smoke_test")
        test_config = _deep_update(test_config, smoke_test_config)

    local_dir = os.path.dirname(test_config_file)
    if "local_dir" in test_config:
        # local_dir is relative to test_config_file
        local_dir = os.path.join(local_dir, test_config["local_dir"])

    result = run_test_config(
        local_dir, project_id, test_name, test_config, smoke_test=smoke_test
    )

    last_logs = result.get("last_logs", "No logs.")
    report_result(
        test_name=test_name,
        status=result.get("status", "invalid"),
        logs=last_logs,
        results=result.get("results", {}),
        artifacts=result.get("artifacts", {}),
    )

    if has_errored(result):
        notify(test_config.get("owner", {}), result)
        raise RuntimeError(last_logs)

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test-config", type=str, required=True, help="Test config file"
    )
    parser.add_argument("--test-name", type=str, help="Test name in config")
    parser.add_argument("--ray-wheels", required=False, type=str,
                        help="URL to ray wheels")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Finish quickly for testing"
    )
    args, _ = parser.parse_known_args()

    if args.ray_wheels:
        os.environ["RAY_WHEELS"] = str(args.ray_wheels)

    run_test(
        test_config_file=args.test_config,
        test_name=args.test_name,
        project_id=GLOBAL_CONFIG["ANYSCALE_PROJECT"],
        smoke_test=args.smoke_test,
    )
