import datetime

from typing import Dict, Optional


def handle_result(created_on: datetime.datetime, category: str,
                  test_suite: str, test_name: str, status: str, results: Dict,
                  artifacts: Dict, last_logs: str) -> Optional[str]:
    assert test_suite == "tune_tests"

    if test_name == "bookkeeping_overhead":
        time_taken = results.get("time_taken", float("inf"))
        if time_taken > 800.:
            return f"Bookkeeping overhead: {time_taken} > 800"

    return None
