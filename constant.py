import os
import typing

from pathlib import Path

import release_tests as rt

# -- Github --
REPO_NAME = "ray-project/ray"
MASTER_BRANCH = "master"
NIGHTLY_VERSION = "0.9.0.dev0"

# -- Release tests --
RELEASE_TEST_DIR = Path(__file__).cwd() / "release_tests"
TEMP_DIR = "/tmp/releaser"

# -- Slack --
DEFAULT_SLACK_CHANNEL = "#bot-release-test"
