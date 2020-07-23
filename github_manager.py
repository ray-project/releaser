import os

from github import Github

from util import run_subprocess

class GithubManager:
    def __init__(self, repo_name):
        self.github = Github(os.environ["GITHUB_TOKEN"])
        self.repo = self.github.get_repo(repo_name)

    def get_latest_commit(self):
        return self.repo.get_branch(branch="master").commit.sha

    def clone(self, url):
        run_subprocess(["git", "clone", url])
