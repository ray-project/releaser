import os
import typing

from pathlib import Path

import release_tests as rt

from context import Context

# -- Github --
REPO_NAME = "ray-project/ray"
MASTER_BRANCH = "master"
NIGHTLY_VERSION = "0.9.0.dev0"

# -- Release tests --
RELEASE_TEST_DIR = Path(__file__).cwd() / "release_tests"
TEMP_DIR = "/tmp/releaser"

# -- Microbenchark --
MICROBENCHMARK = "microbenchmark"

release_tests = [
    MICROBENCHMARK
]


def get_test_controller(context: Context):
    if context.test_type == MICROBENCHMARK:
        return rt.MicrobenchmarkTestController(context)
