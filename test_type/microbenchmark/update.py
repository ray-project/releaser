import logging
import os
import time
import traceback

from datetime import datetime
from pathlib import Path

import boto3
import click

from botocore.exceptions import ClientError
from slack import WebClient
from slack.errors import SlackApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
CHANNEL = "#bot-release-test"

class SlackBot:
    def __init__(self):
        self.client = WebClient(token=SLACK_BOT_TOKEN)

    def send_message(self, text):
        try:
            response = self.client.chat_postMessage(
                channel=CHANNEL,
                text=text)
            print(response)
        except SlackApiError as e:
            # You will get a SlackApiError if "ok" is False
            assert e.response["ok"] is False
            assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
            print(f"Got an error: {e.response['error']}")


class ResultUpdater:
    def __init__(self,
                 *,
                 log_file_path,
                 ray_version,
                 commit,
                 ray_branch,
                 session_id):
        self.log_file_path = log_file_path
        self.slackbot = SlackBot()
        self.ray_branch = ray_branch
        self.ray_version = ray_version
        self.session_id = session_id
        self.commit = commit
        self.s3 = boto3.client("s3")
        self.project_type = "microbenchmark"
        self.bucket = "release-pipeline-result"

    def process(self):
        results = self._process_microbenchmark_log()
        results = "".join(results)
        current_time = self._get_current_time()
        result_string = (
            f"Releaser successfully Ran the test! Here is the result.\n\n"
            f"*Summary*\n"
            f"Test Type: Microbenchmark\n"
            f"Session Name: {self.session_id}\n"
            f"Ray Version: {self.ray_version}\n"
            f"Ray Branch: {self.ray_branch}\n"
            f"Ray Commit: {self.commit}\n"
            f"Created: {current_time}\n\n"
            f"*Result*\n"
            f"{results}")
        self.slackbot.send_message(result_string)
        result_file_path = self._write_result(results)
        self._backup_result(result_file_path, current_time)

    def _write_result(self, results):
        file_path = "/tmp/microbenchmark.txt"
        with open(file_path, "w") as file:
            file.write(results)
        return file_path

    def _backup_result(self, file_path, current_time):
        try:
            self.s3.upload_file(file_path, self.bucket, self._build_key(current_time))
        except ClientError as e:
            logger.error(e)
            logger.error("S3 Client Error occured")
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())

    def _process_microbenchmark_log(self):
        microbenchmark_starting_words = ["single", "multi", "1:1", "1:n", "n:n"]
        results = []
        with open(self.log_file_path) as file:
            for line in file:
                from pprint import pprint
                if line.split(' ')[0] in microbenchmark_starting_words:
                    results.append(line)
        return results

    def _build_key(self, current_time):
        return (
            f"{self.project_type}/?time={current_time}"
            f"?session_name={self.session_id}"
            f"?commit={self.commit}"
            f"?branch={self.ray_branch}"
            f"?version={self.ray_version}")

    def _get_current_time(self):
        now = datetime.now()
        return now.strftime("%m-%d-%Y-%H:%M:%S")


def find_latest_command_log_file():
    dirpath = Path("/tmp")
    assert dirpath.is_dir()
    file_list = []
    for file_candidate in dirpath.iterdir():
        if (file_candidate.is_file()
                and file_candidate.name.startswith("ray_command_output")
                and file_candidate.name.endswith(".out")):
            file_list.append(file_candidate)
    latest_file = sorted(file_list)[-1]
    log_file_path = latest_file.absolute()
    return log_file_path


@click.command()
@click.option(
    "--ray-version",
    required=True
)
@click.option(
    "--commit",
    required=True
)
@click.option(
    "--ray-branch",
    required=True
)
@click.option(
    "--session-id",
    required=True
)
def update(ray_version, commit, ray_branch, session_id):
    result_updater = ResultUpdater(
        log_file_path=find_latest_command_log_file(),
        ray_version=ray_version,
        commit=commit,
        ray_branch=ray_branch,
        session_id=session_id
    )
    result_updater.process()


if __name__ == "__main__":
    update()
