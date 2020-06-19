import time

from dataclasses import dataclass

import config
import release_tests

from context import Context
from controller import TestController
from github_manager import GithubManager
from util import (
    cd,
    run_subprocess,
    check_project_created,
    check_test_type_exist,
    get_test_dir
)


class Runner:
    def __init__(self, context: Context):
        # Context of this release test.
        self.context = context
        # The release test controller.
        self.test_controller: TestController = config.get_test_controller(context)
        # The folder in which release tests are defined.
        self.test_folder = get_test_dir(self.context.test_type)

        check_project_created(self.test_folder)

    def run(self):
        print(f"Session Name {self.context.session_name} is spawned.")
        print(f"It will run {self.context.test_type} test.")
        with cd(self.test_folder):
            self.test_controller.run()

