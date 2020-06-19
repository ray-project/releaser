import click

import config
import release_tests

from context import Context
from runner import Runner
from updater import PostProcessor, SlackBot, S3Updater

@click.group()
def cli():
    pass


# -- Default CLI --
@cli.command()
@click.option(
    "--test-type",
    required=True,
    type=click.Choice(config.release_tests),
)
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
def stop(test_type: str, session_name: str, terminate: bool):
    PostProcessor.stop(test_type, session_name, terminate=terminate)


@cli.command()
@click.option(
    "--test-type",
    required=True,
    type=click.Choice(config.release_tests),
)
@click.option(
    "--session-name",
    required=True,
    type=str
)
def update(test_type: str, session_name: str):
    slackbot = SlackBot()
    s3_updater = S3Updater(test_type)
    PostProcessor(test_type, slackbot, s3_updater).update(session_name)


# -- Command Runner CLI --
@cli.group()
def run():
    pass


@run.command()
@click.option(
    "--session-id",
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
def microbenchmark(session_id: str,
                   ray_version: str,
                   commit: str,
                   ray_branch: str):
    context = Context(
        test_type=config.MICROBENCHMARK,
        version=ray_version, commit=commit,
        branch=ray_branch, session_id=session_id)
    runner = Runner(context)
    runner.run()


if __name__ == "__main__":
    cli()
