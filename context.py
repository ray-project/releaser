import os

from dataclasses import dataclass

import config

from github_manager import GithubManager
from util import check_test_type_exist, SessionNameBuilder

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
    test_type: str = None
    github_token: str = os.environ.get("GITHUB_TOKEN")
    # This value should not be explictly set.
    session_name: str = None

    def post_process(self):
        """Implement this method to do post validation."""
        pass

    def __post_init__(self):
        check_test_type_exist(self.test_type)
        self.session_name = SessionNameBuilder.build_session_name(
            self.test_type,
            self.version,
            self.commit,
            self.branch,
            self.session_id)

        if (self.version is None
                and self.commit is None
                and self.branch is None):
            # Get the commit from github.
            if self.github_token is None:
                raise EnvironmentError(
                    "We deteced you didn't pass the Github commit. "
                    "In this case, you need to provide a Github token env variable "
                    "export GITHUB_TOKEN='[token]' to get the latest commit hash."
                )
            self.branch = config.MASTER_BRANCH
            self.version = config.NIGHTLY_VERSION
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
        self.post_process()

