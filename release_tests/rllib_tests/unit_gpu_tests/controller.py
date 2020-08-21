from controller import TestController
from context import Context
from util import run_subprocess

# MICROBENCHMARK_LOG_IDENTIFIER = ["single", "multi", "1:1", "1:n", "n:n"]


class RLlibUnitGPUTestController(TestController):
    def __init__(self, context: Context):
        self.context = context

    def run(self):
        run_subprocess([
            "anyscale",
            "start", "--session-name", f"{self.context.session_name}",
            "--run",
            "\"bash run.sh\""
        ])

    def process_logs(self, log_output_lines: list) -> str:
        #results = []
        #for line in log_output_lines:
        #    if line.split(' ')[0] in MICROBENCHMARK_LOG_IDENTIFIER:
        #        results.append(line)
        #return "\n".join(results)
        pass

    def generate_slackbot_message(self,
                                  results: str,
                                  current_time) -> str:
        #result_string = (
        #    f"Releaser successfully ran the test! Here is the result.\n\n"
        #    f"*Summary*\n"
        #    f"Test Type: {self.context.test_type}\n"
        #    f"Session Name: {self.context.session_id}\n"
        #    f"Ray Version: {self.context.version}\n"
        #    f"Ray Branch: {self.context.branch}\n"
        #    f"Ray Commit: {self.context.commit}\n"
        #    f"Created: {current_time}\n\n"
        #    f"*Result*\n"
        #    f"{results}")
        #return result_string
        pass
