from typing import List

import click

import api
from release_tests import registry

from context import Context
from runner import Runner

@click.group()
def cli():
    pass


# -- Default CLI --
@cli.command()
@click.option(
    "--test-type",
    required=True,
    type=click.Choice(registry.release_tests),
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
    api.stop(test_type, session_name, terminate)


@cli.command()
@click.option(
    "--test-type",
    required=True,
    type=click.Choice(registry.release_tests),
)
@click.option(
    "--session-name",
    required=True,
    type=str
)
def update(test_type: str, session_name: str):
    api.update(test_type, session_name)


@cli.command()
@click.option(
    "--test-type",
    required=False,
    default=None,
    type=click.Choice(registry.release_tests),
)
@click.option(
    "--all",
    required=False,
    default=False,
    is_flag=True,
    type=bool
)
def cleanup(test_type: str, all: bool):
    api.cleanup(test_type, all)


@cli.command()
@click.option(
    "--test-type",
    required=False,
    default=None,
    type=click.Choice(registry.release_tests),
)
def kill_old_sessions(test_type: str):
    api.force_terminate_old_sessions(test_type)


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
    api.run_microbenchmark(session_id=session_id,
                           ray_version=ray_version,
                           commit=commit,
                           ray_branch=ray_branch)


if __name__ == "__main__":
    cli()
