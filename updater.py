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

import config

from controller import TestController
from context import Context
from util import SessionNameBuilder
from util import cd, run_subprocess, check_test_type_exist, check_project_created, get_test_dir

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
            assert response.status_code == 200
        except SlackApiError as e:
            # You will get a SlackApiError if "ok" is False
            assert e.response["ok"] is False
            assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
            print(f"Got an error: {e.response['error']}")
            logger.error("Slackbot report has failed!!")


class S3Updater:
    def __init__(self, test_type):
        check_test_type_exist(test_type)
        self.s3 = boto3.client("s3")
        self.test_type = test_type
        self.bucket = "release-pipeline-result"

    def backup_result(self,
                      file_path,
                      current_time,
                      session_info: SessionNameBuilder.Session_info, ):
        try:
            self.s3.upload_file(
                str(file_path),
                self.bucket,
                self._build_key(session_info, current_time))
        except ClientError as e:
            logger.error(e)
            logger.error("S3 Client Error occured")
            logger.error(traceback.format_exc())
            logger.error("S3 update has failed!!")
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())
            logger.error("S3 update has failed!!")

    def _build_key(self, session_info: SessionNameBuilder.Session_info, current_time):
        return (
            f"{session_info.test_type}/?time={current_time}"
            f"?session_id={session_info.session_id}"
            f"?commit={session_info.commit}"
            f"?branch={session_info.branch}"
            f"?version={session_info.version}")


class PostProcessor:

    def __init__(self, test_type, slackbot: SlackBot, s3_updater: S3Updater):
        check_test_type_exist(test_type)
        self.test_dir = get_test_dir(test_type)
        self.test_type = test_type
        self.slackbot = slackbot
        self.s3_updater = s3_updater

    def update(self, session_name: str):
        # Get the context from the session name
        session_info = SessionNameBuilder.parse_session_name(session_name)
        context = self._get_context_from_session_info(session_info)
        controller: TestController = config.get_test_controller(context)

        # Download logs and parses it.
        log_output = self.download_logs(context.test_type, session_name)
        results = controller.process_logs(log_output.split("\n"))

        # Update it through the slackbot.
        current_time = self._get_current_time()
        result_string = controller.generate_slackbot_message(results, current_time)

        # Update it to S3.
        result_file_path = controller.write_result(results)
        self.s3_updater.backup_result(
            result_file_path, current_time, session_info)
        self.slackbot.send_message(result_string)

    def download_logs(self, test_type, session_name):
        with cd(get_test_dir(test_type)):
            output, _, _ = run_subprocess(
                ["anyscale", "session", "logs"],
                print_output=False)
        return output

    def _get_current_time(self):
        now = datetime.now()
        return now.strftime("%m-%d-%Y-%H:%M:%S")

    def _get_context_from_session_info(self, session_info: SessionNameBuilder.Session_info) -> Context:
        return Context(
            version=session_info.version,
            commit=session_info.commit,
            branch=session_info.branch,
            session_id=session_info.session_id,
            test_type=session_info.test_type)


    @classmethod
    def stop(cls, test_type: str, session_name: str, terminate: bool = False):
        check_test_type_exist(test_type)
        test_dir = get_test_dir(test_type)
        check_project_created(test_dir)

        with cd(test_dir):
            command = [
                "anyscale", "stop", f"{session_name}"
            ]
            if terminate:
                command.append("--terminate")
            run_subprocess(command)
