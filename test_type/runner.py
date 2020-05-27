import time

from uuid import uuid4
from dataclasses import dataclass

import config

from github_manager import GithubManager
from util import cd, run_subprocess, parse_cluster_status

@dataclass
class Parameters:
    version: str
    commit: str
    branch: str
    slackbot_token: str

    def __post_init__(self):
        if (self.version is None
                and self.commit is None
                and self.branch is None):
            # Get the commit from github.
            self.branch = "master"
            self.version = "0.9.0.dev0"
            self.commit = GithubManager(config.REPO_NAME).get_latest_commit()
        else:
            assert self.version and self.commit and self.branch, (
                "You should either provide all version commit branch "
                "or should not provide any of them. If you don't provide "
                "any of them, it will find the latest commit."
                f"version: {self.version}\n"
                f"commit: {self.commit}\n"
                f"branch: {self.branch}"
            )


class Runner:
    def __init__(self, session_name: str = None, project_type: str = None):
        self.project_type = project_type
        self.project_folder = config.get_config_path(project_type)
        self.session_name = str(uuid4()) if session_name is None else session_name
        self.check_project_created()

    def check_project_created(self):
        project_id_path = self.project_folder / "ray-project" / "project-id"
        if not project_id_path.exists():
            raise Exception(
                f"{self.project_folder} project hasn't been created.\n"
                f"You should create a project using anyscale init inside the"
                f"project folder."
            )

    def check_cluster_is_ready(self):
        output, error, return_code = run_subprocess([
            "anyscale",
            "list", "sessions", "--all"
        ], print_output=False)
        active, status = parse_cluster_status(output, self.session_name)
        print("========================================================")
        print(f"Current Status: {status}")
        return active and status is None

    def run(self, param):
        print(f"Session Name {self.session_name} is spawned.")
        print(f"It will run {self.project_type} test.")
        with cd(self.project_folder):
            self.run_session_start(param)

            waiting_time = 0
            # Wait for maximum 15 minutes.
            MAX_WAITING_TIME = 900
            while (not self.check_cluster_is_ready() 
                    and waiting_time <= MAX_WAITING_TIME):
                print(f"Waiting for cluster ready for {waiting_time} seconds...")
                delta = 10.0
                time.sleep(delta)
                waiting_time += delta

            if not self.check_cluster_is_ready():
                raise Exception(
                    f"Cluster was not ready within {waiting_time} "
                    f"seconds. This is usually due to cluster hang. "
                    f"Please troubleshoot the issue."
                )
            print(f"\nCluster is ready after {waiting_time} seconds")
            self.run_command(param)

    def run_session_start(self, param):
        raise NotImplementedError("Should be implemented in the child class.")

    def run_command(self, param):
        raise NotImplementedError("Should be implemented in the child class.")

    def store_logs(self):
        raise NotImplementedError("Should be implemented in the child class.")

    def report_to_slack_channel(self):
        raise NotImplementedError("Should be implemented in the child class.")

    def update(self):
        with cd(self.project_folder):
            run_subprocess(["anyscale", "session", "logs", "--name", f"{self.session_name}"])

    def stop(self):
        with cd(self.project_folder):
            run_subprocess(["anyscale", "stop", f"{self.session_name}"])

    def terminate(self):
        with cd(self.project_folder):
            run_subprocess(["anyscale", "stop", f"{self.session_name}", "--terminate"])

