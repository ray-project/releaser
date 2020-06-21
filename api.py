import traceback

from typing import List

import constant
from release_tests import registry

from context import Context
from runner import Runner
from updater import PostProcessor, SlackBot, S3Updater
from scanner import Scanner

# -- Release Test Run APIs --
def run_microbenchmark(session_id: str = None,
                       ray_version: str = None,
                       commit: str = None,
                       ray_branch: str = None) -> None:
    context = Context(
        test_type=registry.MICROBENCHMARK,
        version=ray_version, commit=commit,
        branch=ray_branch, session_id=session_id)
    print(context)
    runner = Runner(context)
    runner.run()


# -- Common APIs --
def stop(test_type: str, session_name: str, terminate: bool) -> None:
    PostProcessor.stop(test_type, session_name, terminate=terminate)


def update(test_type: str, session_name: str) -> None:
    slackbot = SlackBot()
    s3_updater = S3Updater(test_type)
    PostProcessor(test_type, slackbot, s3_updater).update(session_name)


def cleanup(test_type: str, run_all: bool) -> None:
    test_candidates = []
    if run_all:
        assert test_type is None, (
            f"Test type shouldn't be given "
            f"when --all option has passed, "
            f"but you passed {test_type}")
        test_candidates = registry.release_tests
    else: # not running all
        assert test_type is not None, (
            f"When --all is not given, you should specify "
            f"the test type. choice: {registry.release_tests}"
        )
        test_candidates.append(test_type)

    slackbot = SlackBot()
    for test_type in test_candidates:
        scanner = Scanner(test_type)
        print(f"Test type, {test_type} will be scanned to be cleaned.")
        completed_sessions: List[str] = scanner.get_completed_sessions()
        for session_name in completed_sessions:
            try:
                print(f"session, {session_name} result will be updated")
                update(test_type, session_name)
            except Exception as e:
                error_msg = (
                    f"Exception occured while updating the test result.\n"
                    f"Test type: {test_type}\n"
                    f"Session Name: {session_name}\n"
                    f"Error Message:{e}\n"
                    f"traceback: {traceback.format_exc()}")
                slackbot.send_message(error_msg)
                raise ValueError(error_msg)

            try:
                print(f"session, {session_name} will be stopped")
                stop(test_type, session_name, terminate=True)
            except Exception as e:
                error_msg = (
                    f"Exception occured while stopping the session.\n"
                    f"Test type: {test_type}\n"
                    f"Session Name: {session_name}\n"
                    f"Error Message:{e}\n"
                    f"traceback: {traceback.format_exc()}")
                slackbot.send_message(error_msg)
                raise ValueError(error_msg)


def force_terminate_old_sessions(test_type: str):
    release_tests = None
    if test_type is None:
        release_tests = registry.release_tests
    else:
        release_tests = [test_type]

    for test_type in release_tests:
        scanner = Scanner(test_type)
        print(f"Test type, {test_type} will be scanned to be killed.")
        for old_session_name in scanner.get_old_sessions():
            print(
                f"Session Name {old_session_name} is "
                "foreced killed because it is old.")
            stop(test_type, old_session_name, terminate=True)
