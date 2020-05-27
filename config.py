import os
import typing

from pathlib import Path

REPO_NAME = "ray-project/ray"

# Project Type
MICROBENCHMARK = "microbenchmark"

test_type_dir = Path(__file__).cwd() / "test_type"
MICROBENCHMARK_DIR = test_type_dir / "microbenchmark"

def get_config_path(test_type: str) -> str:
    if test_type == MICROBENCHMARK:
        return MICROBENCHMARK_DIR
    else:
        raise Exception("Wrong test type is given.")
