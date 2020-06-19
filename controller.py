from abc import ABC

from context import Context
from util import SessionNameBuilder

class TestController(ABC):
    def run(self):
        raise NotImplementedError(
            "Test Controller class shouldn't be instantiated directly.")

    def process_logs(self, log_output_lines: list) -> str:
        raise NotImplementedError(
            "Test Controller class shouldn't be instantiated directly.")

    def generate_slackbot_message(self,
                                  results: str,
                                  current_time) -> str:
        raise NotImplementedError(
            "Test Controller class shouldn't be instantiated directly.")

    def write_result(self, result: str) -> None:
        raise NotImplementedError(
            "Test Controller class shouldn't be instantiated directly.")

