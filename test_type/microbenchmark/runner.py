import os

from test_type.runner import Runner
from util import run_subprocess


class MicroBenchmarkRunner(Runner):
    def run_session_start(self, param):
        run_subprocess([
            "anyscale",
            "start", "--session-name", f"{self.session_name}"
        ])

    def run_command(self, param):
        run_subprocess([
            "anyscale", "run", "--session-name", f"{self.session_name}",
            "run",
            "--ray_version", f"{param.version}",
            "--commit", f"{param.commit}",
            "--ray_branch", f"{param.branch}",
            "--session_id", f"{self.session_name}",
            "--slack_bot_token", f"{param.slackbot_token}"
        ])
