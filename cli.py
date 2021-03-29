import datetime
import os
import subprocess
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from functools import partial
from pprint import pprint
from typing import Dict, Optional

import jinja2
import requests
import toml
import typer
import yaml
from anyscale.api import get_api_client
from anyscale.credentials import load_credentials
from anyscale.sdk.anyscale_client.sdk import AnyscaleSDK
from dotenv import load_dotenv

load_dotenv()


###### Global Variables
PREFIX = os.environ.get("RELEASER_PREFIX", "release-automation")
# Update the local ray dir if you want to test local changes to release tests
LOCAL_RAY_DIR = os.environ.get("RELEASER_LOCAL_RAY_DIR", "ray")
CLI_TOKEN = os.environ.get("ANYSCALE_CLI_TOKEN") or load_credentials()

app = typer.Typer()
global_context: Dict[str, str] = dict()
anyscale_sdk = AnyscaleSDK(CLI_TOKEN)
ansycale_api_client = get_api_client()
######

###### Helper Functions
def run_shell(*args, **kwargs):
    default_kwargs = dict(
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        executable="/bin/bash",
        env=os.environ,
    )
    default_kwargs.update(kwargs)

    proc = subprocess.run(
        *args,
        **default_kwargs,
    )
    if proc.returncode != 0:
        typer.secho(f"Failed to run {args}", fg=typer.colors.BRIGHT_RED)
        typer.secho(proc.stdout, fg=typer.colors.RED)
        raise typer.Exit(1)
    return proc


run_shell_stream = partial(run_shell, stdout=None, stderr=None)
color_print = partial(typer.secho, fg=typer.colors.MAGENTA)


def _get_config():
    """Given a config file:
    - replace all placeholder with global_context
    - expand test cases into test suites
    """
    with open("config.toml") as f:
        raw_config = toml.loads(f.read())

    rendered_config = {}
    for name, suite in raw_config.items():
        # Simple test suite doesn't have many cases.
        # For example microbenchmark is a simple test.
        raw_exec_command = jinja2.Template(suite["exec_cmd"])
        rendered_config[name] = suite

        is_simple_test_suite = "case" not in suite.keys()
        if is_simple_test_suite:
            rendered_config[name]["workload_exec_cmds"] = {
                "basic": raw_exec_command.render(ctx=global_context)
            }
        else:
            workload_cmds = {}
            workload_configs = {}
            for local_ctx in suite["case"]:
                ctx = global_context.copy()
                ctx.update(local_ctx)
                workload_name = local_ctx["workload"]
                # Construct data for a new test suite using case data
                rendered_exec_cmd = raw_exec_command.render(ctx=ctx)

                workload_cmds[workload_name] = rendered_exec_cmd
                workload_configs[workload_name] = ctx
            rendered_config[name]["workload_exec_cmds"] = workload_cmds
            rendered_config[name]["workload_configs"] = workload_configs
            suite.pop("case")

        suite.pop("exec_cmd")
    return rendered_config


def _setup_env():
    """Get workload env dict"""
    os.environ["RAY_WHEEL"] = wheel_url(
        global_context["ray_version"],
        global_context["git_branch"],
        global_context["git_commit"])
    os.environ["RAY_VERSION"] = global_context["ray_version"]

    os.environ["ANYSCALE_USER"] = os.environ.get(
        "ANYSCALE_USER", "eng@anyscale.com")
    expiry = datetime.datetime.now() + datetime.timedelta(days=1)
    os.environ["ANYSCALE_EXPIRATION"] = expiry.strftime("%Y-%m-%d")


@contextmanager
def cd(path):
    path = os.path.expanduser(path)
    saved_path = os.getcwd()

    os.chdir(path)
    yield
    os.chdir(saved_path)


def wheel_url(ray_version, git_branch, git_commit):
    return f"https://s3-us-west-2.amazonaws.com/ray-wheels/" \
           f"{git_branch}/{git_commit}/" \
           f"ray-{ray_version}-cp37-cp37m-manylinux2014_x86_64.whl"


def wheel_exists(ray_version, git_branch, git_commit):
    url = wheel_url(ray_version, git_branch, git_commit)
    return requests.head(url).status_code == 200


######


# This function runs before each CLI invocation
@app.callback()
def ensure_repo(
    git_branch: str = "master",
    git_commit: Optional[str] = None,
    git_org: str = "ray-project",
    git_skip_checkout: bool = False,
):
    color_print("Running precondition check...")

    # This ray clone is used to find recent commits
    # We thus don't use LOCAL_RAY_DIR here
    if not os.path.exists("ray"):
        color_print("💾 Ray repository not found. Cloning...")
        run_shell(f"git clone https://github.com/{git_org}/ray.git")

    with cd("ray"):
        if git_skip_checkout:
            color_print("💰 Skipping git checkout")
        else:
            color_print(f"💰 Checking out {git_branch}")
            run_shell(
                f"git fetch && git checkout {git_branch} && git pull origin {git_branch}"
            )
            if git_commit:
                run_shell(f"git checkout {git_commit}")
            else:
                # We want to find the latest commit with wheels available
                for commit in run_shell(
                    r'git log --oneline -20 --pretty=format:"%H"'
                ).stdout.splitlines(keepends=False):
                    commit = commit.strip()
                    run_shell(f"git checkout {commit}")
                    exec(
                        run_shell('grep "__version__ = " python/ray/__init__.py').stdout
                    )
                    if wheel_exists(locals()["__version__"], git_branch, commit):
                        break
                else:
                    color_print("Can't find a commit with wheels available!")
                    raise typer.Exit(1)

        latest_commit = run_shell(
            r'git --no-pager log -1 --oneline --no-color --pretty=format:"%h - %an, %cr: %s"'
        ).stdout.strip()
        color_print(f'🧬 Latest commit (with wheels) is "{latest_commit}"')

        global_context["git_branch"] = git_branch
        global_context["git_commit"] = run_shell("git rev-parse HEAD").stdout.strip()

        exec(run_shell('grep "__version__ = " python/ray/__init__.py').stdout)
        global_context["ray_version"] = locals()["__version__"]

        color_print(f"📖 Running with context: {global_context}")


@app.command("suite:validate")
def validate_tests():
    """Validate the test suites from `config.toml`"""
    config = _get_config()
    with cd(LOCAL_RAY_DIR):
        for name, entry in config.items():
            cluster_file = os.path.join(entry["base_dir"], entry["cluster_config"])

            assert os.path.exists(
                cluster_file
            ), f"Validating {name} failed: cluster config file {os.path.abspath(cluster_file)} doesn't exist"

            with open(cluster_file) as f:
                yaml.safe_load(f)

    color_print("😃 Validation successful! Listing all suites.")

    test_suite = {
        key: list(value["workload_exec_cmds"].keys()) for key, value in config.items()
    }
    pprint(test_suite)


def _create_or_get_project_id(project_name: str):
    known_project_id = None

    my_user_id = ansycale_api_client.get_user_info_api_v2_userinfo_get().result.id
    project_id_found = anyscale_sdk.search_projects(
        projects_query={"name": {"equals": project_name}}
    ).results
    for proj in project_id_found:
        if proj.creator_id == my_user_id:
            known_project_id = proj.id
    if known_project_id is None:
        known_project_id = anyscale_sdk.create_project({"name": project_name}).result.id
    return known_project_id


def run_case(base_dir, execution_steps):
    print(f"Thread {threading.get_ident()} running {execution_steps}")
    with cd(os.path.join(LOCAL_RAY_DIR, base_dir)):
        for step in execution_steps:
            run_shell_stream(step)


@app.command("suite:run")
def run_test(
    name: str,
    workload: Optional[str] = None,
    wait: bool = True,
    stop: bool = True,
    dryrun: bool = False,
):
    """Run a single test suite given `name`."""
    # Validation
    validate_tests()
    config = _get_config()
    all_suites = list(config.keys())
    assert name in all_suites, f"{name} not found. Available suites are {all_suites}."

    suite_config = config[name]
    base_dir = suite_config["base_dir"]
    cluster_config = suite_config["cluster_config"]

    project_id = _create_or_get_project_id(project_name=f"{PREFIX}-{name}")

    _setup_env()

    workload_exec_steps = {}
    cleanup_steps = []
    for workload_name, workload_cmd in suite_config["workload_exec_cmds"].items():
        if workload and workload_name != workload:
            continue

        workload_config = suite_config["workload_configs"][workload_name]

        workload_cluster_config = workload_config.get(
            "cluster_config", cluster_config)

        # session_name format: gitsha-timestamp
        session_name = (
            workload_name
            + "-"
            + global_context["git_commit"][:6]
            + f"-{int(time.time())}"
        )
        local_exec_steps = []
        local_exec_steps.append(
            # Create a new anyscale session
            f"anyscale up --cloud-name anyscale_default_cloud --config {workload_cluster_config} {session_name}"
        )

        exec_options = "" if wait else "--tmux"
        # Might want to swap this to run on every node (at least for the command to install ray.)
        exec_options += " --stop" if stop else " "
        local_exec_steps.append(
            f"anyscale exec {exec_options} --session-name {session_name} -- '{workload_cmd}'"
        )
        workload_exec_steps[workload_name] = local_exec_steps

        if wait and stop:
            cleanup_steps.append(f"anyscale down --terminate {session_name} || true")

    if workload and not workload_exec_steps:
        raise ValueError(f"Workload {workload} not found in test suite {name}")

    global_execution_steps = [
        # Re-instantiate the project because it's already registered in the past.
        f"echo 'project_id: {project_id}' > .anyscale.yaml",
    ]

    color_print(f"🗺 Execution plan (within ray/{base_dir})")
    for step in global_execution_steps:
        typer.echo("\t" + step)
    for name, workload_cmds in workload_exec_steps.items():
        typer.echo(f"\t{name}:")
        for command in workload_cmds:
            typer.echo(f"\t\t{command}")

    if dryrun:
        raise typer.Exit()

    color_print(f"🚀 Kicking off")
    for command in global_execution_steps:
        with cd(os.path.join(LOCAL_RAY_DIR, base_dir)):
            run_shell_stream(command)
    try:
        with ProcessPoolExecutor(max_workers=len(workload_exec_steps)) as executor:
            for workload_cmds in workload_exec_steps.values():
                executor.submit(run_case, base_dir, workload_cmds)
    finally:
        with cd(os.path.join("ray", base_dir)):
            for command in cleanup_steps:
                try:
                    run_shell_stream(command)
                except:
                    pass


if __name__ == "__main__":
    app()
