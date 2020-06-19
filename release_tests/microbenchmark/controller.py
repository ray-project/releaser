import os

from dataclasses import dataclass
from pathlib import Path

import config

from controller import TestController
from context import Context
from util import run_subprocess, SessionNameBuilder

MICROBENCHMARK_LOG_IDENTIFIER = ["single", "multi", "1:1", "1:n", "n:n"]


class MicrobenchmarkTestController(TestController):
    def __init__(self, context: Context):
        self.context = context

    def run(self):
        run_subprocess([
            "anyscale",
            "start", "--session-name", f"{self.context.session_name}",
            "--run", "run",
            "--ray_version", f"{self.context.version}",
            "--ray_branch", f"{self.context.branch}",
            "--commit", f"{self.context.commit}"
        ])

    def process_logs(self, log_output_lines: list) -> str:
        results = []
        for line in log_output_lines:
            if line.split(' ')[0] in MICROBENCHMARK_LOG_IDENTIFIER:
                results.append(line)
        return "\n".join(results)

    def generate_slackbot_message(self,
                                  results: str,
                                  current_time) -> str:
        result_string = (
            f"Releaser successfully Ran the test! Here is the result.\n\n"
            f"*Summary*\n"
            f"Test Type: {self.context.test_type}\n"
            f"Session Name: {self.context.session_id}\n"
            f"Ray Version: {self.context.version}\n"
            f"Ray Branch: {self.context.branch}\n"
            f"Ray Commit: {self.context.commit}\n"
            f"Created: {current_time}\n\n"
            f"*Result*\n"
            f"{results}")
        return result_string

    def write_result(self, result: str) -> None:
        temp_dir = Path(config.TEMP_DIR)
        temp_dir.mkdir(exist_ok=True)

        file_path = temp_dir / f"{self.context.test_type}.txt"
        with open(file_path, "w") as file:
            file.write(result)
        return file_path

