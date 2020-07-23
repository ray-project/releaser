import os
import typing

from pathlib import Path

# -- Github --
REPO_NAME = "ray-project/ray"
MASTER_BRANCH = "master"
NIGHTLY_VERSION = "0.9.0.dev0"
RAY_REPO_URL = "https://github.com/ray-project/ray.git"

# -- Release tests --
TEMP_DIR = "/tmp/releaser"
CONFIG_FILE = "{}/config.txt".format(TEMP_DIR)

# -- Slack --
DEFAULT_SLACK_CHANNEL = "#bot-release-test"
