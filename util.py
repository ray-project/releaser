import os

from collections import namedtuple
from subprocess import Popen, PIPE
from uuid import uuid4

import config

class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, path):
        self.path = os.path.expanduser(path)

    def __enter__(self):
        self.saved_path = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.saved_path)


def check_project_created(project_folder: str) -> None:
    project_id_path = project_folder / "ray-project" / "project-id"
    if not project_id_path.exists():
        raise Exception(
            f"{project_folder} project hasn't been created.\n"
            f"You should create a project using anyscale init inside the"
            f"project folder."
        )


def check_test_type_exist(test_type: str) -> None:
    assert test_type in config.release_tests, (
        f"Project type {test_type} doesn't exist. " 
        f"Existing projects: {config.release_tests}"
    )


def get_test_dir(test_type: str) -> str:
    return config.RELEASE_TEST_DIR / test_type


def run_subprocess(command: list, print_output: bool = True):
    unflattened_command = ' '.join(command)
    if print_output:
        print(f"\n=====Command Running=====\n{unflattened_command}")
    process = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    if print_output:
        print("\n=======Live Output======")
    while print_output:
        output = process.stdout.readline()
        if output == b'' and process.poll() is not None:
            break
        if output:
            print(output.decode().strip())

    if print_output:
        print("\n\n=========Done=======")
    output, error = process.communicate()

    output = output.decode().strip()
    error = error.decode().strip()
    return_code = process.returncode
    if print_output:
        print(f"Return Code: {str(return_code)}".strip())
        print(f"Error\n{error}".strip())
    return output, error, return_code


class SessionNameBuilder:

    Session_info = namedtuple(
    "session_info",
    ["test_type", "version", "commit", "branch", "session_id"])

    @classmethod
    def build_session_name(cls, test_type, version, commit, branch, session_id):
        return (
            f"{test_type}_" # Underscore is used to label this test with test_name.
            f"{version}_"
            f"{commit}_"
            f"{branch}_"
            f"{str(uuid4()) if session_id is None else session_id}")

    @classmethod
    def parse_session_name(cls, session_name):
        # Note the session name has to be built by `build_session_name` classmethod
        test_type, version, commit, branch, session_id = session_name.split("_")
        return cls.Session_info(
            test_type=test_type,
            version=version,
            commit=commit,
            branch=branch,
            session_id=session_id)
