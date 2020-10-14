import os
from urllib.parse import parse_qs
import subprocess
from functools import partial
from typing import Optional, Dict
from contextlib import contextmanager
import time
from pprint import pprint
import json

import yaml
import toml
import typer
import jinja2
import requests
from dotenv import load_dotenv

load_dotenv()

###### Global Variables
app = typer.Typer()
global_context: Dict[str, str] = dict()
PREFIX = "release-automation"
CLI_TOKEN = (
    os.environ.get("ANYSCALE_CLI_TOKEN")
    or json.load(open(os.path.expanduser("~/.anyscale/credentials.json")))["cli_token"]
)
######

###### Helper Functions
run_shell = partial(
    subprocess.run,
    check=True,
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    encoding="utf-8",
    executable="/bin/bash",
)
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
        is_simple_test_suite = "case" not in suite.keys()
        raw_exec_command = jinja2.Template(suite["exec_cmd"])

        if is_simple_test_suite:
            rendered_config[name] = suite
            rendered_config[name]["exec_cmd"] = raw_exec_command.render(
                ctx=global_context
            )
        else:
            for local_ctx in suite["case"]:
                ctx = global_context.copy()
                ctx.update(local_ctx)

                # Construct data for a new test suite using case data
                suite_name = "-".join([name] + list(local_ctx.values()))
                rendered_exec_cmd = raw_exec_command.render(ctx=ctx)

                # Add this new test suite the config
                new_suite = suite.copy()
                new_suite.pop("case")
                new_suite["exec_cmd"] = rendered_exec_cmd

                rendered_config[suite_name] = new_suite

    return rendered_config


@contextmanager
def cd(path):
    path = os.path.expanduser(path)
    saved_path = os.getcwd()

    os.chdir(path)
    yield
    os.chdir(saved_path)


######


@app.callback()
def ensure_repo(
    git_branch: str = "master",
    git_commit: Optional[str] = None,
    git_org: Optional[str] = "ray-project",
):
    color_print("Running precondition check...")

    if not os.path.exists("ray"):
        color_print("💾 Ray repository not found. Cloning...")
        run_shell(f"git clone https://github.com/{git_org}/ray.git")

    with cd("ray"):
        color_print(f"💰 Checking out {git_branch}")
        run_shell(
            f"git fetch && git checkout {git_branch} && git pull origin {git_branch}"
        )
        if git_commit:
            run_shell(f"git checkout {git_commit}")

        latest_commit = run_shell(
            r'git --no-pager log -1 --oneline --no-color --pretty=format:"%h - %an, %cr: %s"'
        ).stdout.strip()
        color_print(f'🧬 Latest commit is "{latest_commit}"')

        global_context["git_branch"] = git_branch
        global_context["git_commit"] = run_shell("git rev-parse HEAD").stdout.strip()

        exec(run_shell('grep "__version__ = " python/ray/__init__.py').stdout)
        global_context["ray_version"] = locals()["__version__"]

        color_print(f"📖 Running with context: {global_context}")


@app.command("suite:validate")
def validate_tests():
    """Validate the test suites from `config.toml`"""
    config = _get_config()
    with cd("ray"):
        for name, entry in config.items():
            cluster_file = os.path.join(entry["base_dir"], entry["cluster_config"])

            assert os.path.exists(
                cluster_file
            ), f"Validating {name} failed: cluster config file {cluster_file} doesn't exist"

            with open(cluster_file) as f:
                yaml.safe_load(f)

    color_print("😃 Validation successful!")
    pprint(config)


@app.command("suite:run")
def run_test(name: str, dryrun: bool = False, wait: bool = True):
    """Run a single test suite given `name`."""
    config = _get_config()
    all_suites = list(config.keys())

    # TODO(simon): re-enable this once fix-cluster-yaml branch merged and wheel produced
    # validate_tests()

    assert name in all_suites, f"{name} not found. Available suites are {all_suites}."

    suite_config = config[name]
    base_dir = suite_config["base_dir"]
    cluster_config = suite_config["cluster_config"]
    exec_cmd = suite_config["exec_cmd"].strip()

    project_name = f"{PREFIX}-{name}"
    session_name = int(time.time())
    known_project_id = None

    get_prj_id_cmd = f"""anyscale list projects --json | jq --raw-output '.[] | select(.name=="{project_name}") | .url  | split("/") | .[-1]'""".strip()

    with cd(os.path.join("ray", base_dir)):
        prj_id = run_shell(get_prj_id_cmd).stdout.strip()
        if len(prj_id):
            known_project_id = prj_id

    execution_steps = []
    if known_project_id:
        execution_steps.append(
            f"echo 'project_id: {known_project_id}' > .anyscale.yaml"
        )
    else:
        execution_steps.append(
            f"rm -f .anyscale.yaml && anyscale init --name {project_name} --config {cluster_config}"
        )
    execution_steps.append(
        f"anyscale up --yes --config {cluster_config} {session_name}"
    )
    execution_steps.append(f"anyscale push")

    if wait:
        execution_steps.append(
            f"(anyscale exec --session-name {session_name} -- {exec_cmd}) 2>&1 | tee {session_name}.log"
        )
        execution_steps.append(f"anyscale down --terminate {session_name}")
        execution_steps.append(
            f"aws s3 cp {session_name}.log s3://ray-travis-logs/periodic_tests/{name}/{session_name}.log"
        )
    else:
        execution_steps.append("echo 'Custom Python Command'")

    color_print(f"🗺 Execution plan (within {base_dir})")
    for step in execution_steps:
        typer.echo("\t" + step)

    if dryrun:
        return

    with cd(os.path.join("ray", base_dir)):
        for step in execution_steps:
            run_shell_stream(step)

        if not wait:
            color_print("🐍 Executing Custom Python Command")
            project_id = run_shell(get_prj_id_cmd).stdout.strip()
            session_data = json.loads(
                run_shell(
                    f"""anyscale list session --json | jq  '.[] | select(.name=="{session_name}")'""".strip()
                ).stdout
            )
            session_id = parse_qs(session_data["tensorboard_url"])["session_id"][0]

            exec_cmd = "; ".join(
                [
                    exec_cmd,
                    f"echo 'project_id: {project_id}' > .anyscale.yaml",
                    f"anyscale down --terminate {session_name}",
                ]
            )

            resp = requests.post(
                f"https://anyscale.dev/api/v2/sessions/{session_id}/execute_shell_command",
                json={"shell_command": exec_cmd},
                cookies={"cli_token": CLI_TOKEN},
            )

            assert resp.status_code == 200, resp.content

            color_print("✅ Command Submitted.")


if __name__ == "__main__":
    app()
