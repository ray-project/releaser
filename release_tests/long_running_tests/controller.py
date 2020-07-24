import os

from dataclasses import dataclass

from controller import TestController
from context import Context
from util import run_subprocess, SessionNameBuilder

MICROBENCHMARK_LOG_IDENTIFIER = ["single", "multi", "1:1", "1:n", "n:n"]


class LongRunningTestsController(TestController):
    def __init__(self, context: Context):
        self.context = context

    def run(self):
        run_subprocess([
            "anyscale",
            "start", "--session-name", f"{self.context.session_name}",
            "--shell",
            "\"bash run.sh "
            f"--ray-version={self.context.version} "
            f"--ray-branch={self.context.branch} "
            f"--commit={self.context.commit}"
            f"--workload={self.context.workload}\""
        ])

    def process_logs(self, log_output_lines: list) -> str:
        pass
        # results = []
        # for line in log_output_lines:
        #     if line.split(' ')[0] in MICROBENCHMARK_LOG_IDENTIFIER:
        #         results.append(line)
        # return "\n".join(results)

    def generate_slackbot_message(self,
                                  results: str,
                                  current_time) -> str:
        pass
        # result_string = (
        #     f"Releaser successfully Ran the test! Here is the result.\n\n"
        #     f"*Summary*\n"
        #     f"Test Type: {self.context.test_type}\n"
        #     f"Session Name: {self.context.session_id}\n"
        #     f"Ray Version: {self.context.version}\n"
        #     f"Ray Branch: {self.context.branch}\n"
        #     f"Ray Commit: {self.context.commit}\n"
        #     f"Created: {current_time}\n\n"
        #     f"*Result*\n"
        #     f"{results}")
        # return result_string
