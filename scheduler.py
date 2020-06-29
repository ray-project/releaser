import traceback
import time

from datetime import datetime, timedelta
from enum import Enum
from typing import List

import yaml

from pydantic import BaseModel

import api
import constant

from release_tests import registry

class SchedulingState(Enum):
    # The test is ready to be invoked.
    READY = 1
    # The test has been scheduled.
    RUN = 2
    # The test is old. It should be terminated.
    OLD = 3


class ReleaseTestConfig(BaseModel):
    test_type: str
    # The interval this test will be started.
    interval: int
    # If true, report the result through a slackbot.
    slackbot_update: bool = False
    # Slack channel to report the result.
    report_channel: str = constant.DEFAULT_SLACK_CHANNEL
    # If true, update the result to S3.
    s3_update: bool = False
    # kwargs required to run this release test.
    kwargs: dict
    # States of this release config.
    state: SchedulingState = SchedulingState.READY
    # The time test should be re-run.
    next_schedule = datetime.now()


class SchedulerConfig(BaseModel):
    cleanup_frequency: int
    tests: List[ReleaseTestConfig]


def parse_scheduler_yaml() -> List[ReleaseTestConfig]:
    with open("schedule.yaml", 'r') as stream:
        try:
            configs = yaml.safe_load(stream)
            return SchedulerConfig.parse_obj(configs)
        except yaml.YAMLError as e:
            print(traceback.format_exc())


class Scheduler:
    def __init__(self):
        self.scheduling_config: SchedulerConfig = parse_scheduler_yaml()
        self.next_cleanup_time: datetime = self._calculate_next_schedule_time(
            seconds=self.scheduling_config.cleanup_frequency)

    def process(self):
        """Process the release test based on its state."""
        # Check if we need to cleanup.
        if datetime.now() > self.next_cleanup_time:
            print("Cleanup time came. Cleanup will happen.")
            self.clean()
            self.next_cleanup_time = self._calculate_next_schedule_time(
                seconds=self.scheduling_config.cleanup_frequency)

        self.run_release_tests()
    
    def clean(self):
        for release_test_config in self.scheduling_config.tests:
            print(f"Test, {release_test_config.test_type} will be cleaned up if necessary.")
            test_type = release_test_config.test_type
            api.cleanup(test_type, False)
            api.force_terminate_old_sessions(test_type)

    def run_release_tests(self):
        for release_test_config in self.scheduling_config.tests:
            if release_test_config.state == SchedulingState.READY:
                print(f"Test, {release_test_config.test_type} will run.")
                # Run release tests if it is ready to run.
                self._run_release_test(release_test_config)
                release_test_config.state = SchedulingState.RUN
                release_test_config.next_schedule = \
                    self._calculate_next_schedule_time(
                        seconds=release_test_config.interval)
            elif (release_test_config.state == SchedulingState.RUN
                    and datetime.now() > release_test_config.next_schedule):
                # If it has run before, check if it needs to re-run in the next round.
                print(f"Test, {release_test_config.test_type} is now ready to run.")
                release_test_config.state = SchedulingState.READY

    def run(self):
        while True:
            try:
                self.process()
            except Exception as e:
                print(f"Error occured while processing: {e}")
                print(traceback.format_exc())
            finally:
                time.sleep(60)

    def _run_release_test(self, test_config: ReleaseTestConfig):
        """Modify this function to add a new test."""
        if test_config.test_type == registry.MICROBENCHMARK:
            api.run_microbenchmark(**test_config.kwargs)

    def _calculate_next_schedule_time(self, hours=None, minutes=None, seconds=None):
        assert hours or minutes or seconds, (
            "No hours/minutes/seconds is given. "
            "You should provide them to calculate "
            "the next schedule time.")
        if not hours: hours = 0
        if not minutes: minutes = 0
        if not seconds: seconds = 0

        return (datetime.now()
                + timedelta(hours=hours, minutes=minutes, seconds=seconds))
