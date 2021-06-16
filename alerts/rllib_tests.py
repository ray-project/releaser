import datetime

from typing import Dict, Optional


def handle_result(created_on: datetime.datetime, category: str,
                  test_suite: str, test_name: str, status: str, results: Dict,
                  artifacts: Dict, last_logs: str) -> Optional[str]:
    assert test_suite == "rllib_tests"

    if not status == "finished":
        return "Test script did not finish successfully."

    return None
