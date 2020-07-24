import os

from dataclasses import dataclass

import constant

from github_manager import GithubManager
from util import SessionNameBuilder

@dataclass
class Context:
    # Note that this class should only have attributes with
    # default values. It is because dataclasses don't allow
    # to put fields without default values after fields with default
    # values. Since all the tests should inherit this class,
    # it should not have attributes without default values.
    version: str = None
    commit: str = None
    branch: str = None
    session_id: str = None
    # Token used to call Github APIs.
    github_token: str = os.environ.get("GITHUB_TOKEN")
    # Release test type.
    test_type: str = None
    # This value should not be explictly set.
    session_name: str = None
    # [Optional] Workload you want to run.
    workload: str = None

    def post_process(self) -> None:
        """Implement this method to do post validation."""
        pass

    def __post_init__(self):
        # If Wheel info is not give, get the latest one from Github.
        if (self.version is None
                and self.commit is None
                and self.branch is None):
            if self.github_token is None:
                raise EnvironmentError(
                    "We deteced you didn't pass the Github commit. "
                    "In this case, you need to provide a Github token env variable "
                    "export GITHUB_TOKEN='[token]' to get the latest commit hash."
                )
            self.branch = constant.MASTER_BRANCH
            self.version = constant.NIGHTLY_VERSION
            self.commit = GithubManager(constant.REPO_NAME).get_latest_commit()
        else:
            assert self.version and self.commit and self.branch, (
                "You should either provide all version commit branch "
                "or should not provide any of them. If you don't provide "
                "any of them, it will find the latest commit."
                f"version: {self.version}\n"
                f"commit: {self.commit}\n"
                f"branch: {self.branch}"
            )

        # Create a session name.
        # NOTE: Session name should always created via SessionNameBuilder class.
        # It is because we want to parse the session name later to get some
        # tags data.
        # TODO(sang): If tags are natively supported, we don't need this anymore.
        self.session_name = SessionNameBuilder.build_session_name(
            self.test_type,
            self.version,
            self.commit,
            self.branch,
            self.session_id)

        # This can be implemented in the child level
        # to define custom post processing logic.
        self.post_process()

