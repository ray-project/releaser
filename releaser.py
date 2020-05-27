import click

from test_type.microbenchmark.cli import microbenchmark

@click.group()
def cli():
    pass


cli.add_command(microbenchmark)


if __name__ == "__main__":
    cli()
