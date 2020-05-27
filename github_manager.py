import os

from github import Github

class GithubManager:
    def __init__(self, repo_name):
        self.github = Github(os.environ["GITHUB_TOKEN"])
        self.repo = self.github.get_repo(repo_name)

    def get_latest_commit(self):
        return self.repo.get_branch(branch="master").commit.sha
