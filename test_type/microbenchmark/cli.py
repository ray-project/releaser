import click
import config

from test_type.runner import Parameters
from test_type.microbenchmark.runner import MicroBenchmarkRunner

@click.group()
def microbenchmark():
    pass


@microbenchmark.command()
@click.option(
    "--session-name",
    required=False,
    default=None,
    type=str
)
@click.option(
    "--ray-version",
    required=False,
    default=None,
    type=str
)
@click.option(
    "--commit",
    required=False,
    type=str,
    default=None
)
@click.option(
    "--ray-branch",
    required=False,
    default=None,
    type=str
)
@click.option( # This option should be removed.
    "--slackbot-token",
    required=True,
    type=str
)
def run(session_name: str,
        ray_version: str,
        commit: str,
        ray_branch: str,
        slackbot_token: str):
    MicroBenchmarkRunner(
        session_name=session_name,
        project_type=config.MICROBENCHMARK
    ).run(Parameters(
        version=ray_version,
        commit=commit,
        branch=ray_branch,
        slackbot_token=slackbot_token
    ))


@microbenchmark.command()
@click.option(
    "--session-name",
    required=True,
    type=str
)
@click.option(
    "--terminate",
    required=False,
    default=False,
    is_flag=True,
    type=bool
)
def stop(session_name: str, terminate: bool):
    if terminate:
        MicroBenchmarkRunner(
            session_name=session_name,
            project_type=config.MICROBENCHMARK
        ).terminate()
    else:
        MicroBenchmarkRunner(
            session_name=session_name,
            project_type=config.MICROBENCHMARK
        ).stop()


@microbenchmark.command()
@click.option(
    "--session-name",
    required=True,
    type=str
)
def update(session_name: str):
    MicroBenchmarkRunner(
        session_name=session_name,
        project_type=config.MICROBENCHMARK
    ).update()
    