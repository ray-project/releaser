# Releaser

Releaser is a command line tool that runs Ray release tests. It uses Github Action to schedule periodic runs and kick off the tests on Ansycale.

## Common Workflows

### Configuring commit

- Run it with Ray nightly wheels: `python cli.py suite:run microbenchmark`. Releaser will find the latest commit with nightly wheel.
- Run it with a given branch: `python cli.py --git-branch releases/1.1.0 suite:run microbenchmark`. Releaser will find the latest commit in that branch that contains a wheel.
- Run it with your own fork: `python cli.py --git-org your-user-name suite:run microbenchmark`. Releaser will clone the specified Ray repo instead of the ray-project's repo.
- Run it with a given commit: `python cli.py --git-commit XXX-COMMIT-SHA suite:run microbenchmark`. Releaser will skip the wheel check
- Disable any sort of auto git-checking: `python cli.py --git-skip-checkout suite:run microbenchmark`. Releaser won't mess with git at all. With this config, you can modify the cloned repo and re-run releaser using the modified Ray repo content.

### Configuring execution

- List all tests: `python cli.py suite:validate`.
- Run it and wait for the result: `python cli.py suite:run microbenchmark`.
- Run it and don't wait for the result: `python cli.py suite:run --no-wait microbenchmark`.
- By default, releaser will shutdown the session after a command finishes (regardless of the exit status of that command). You can override this behavior with `python cli.py suite:run --no-stop microbenchmark`.
- By default, releaser will run all test cases in parallel for a given suite. To limit the specific case(s) to be run, you can modify the `config.toml` by commenting out test cases you don't want to be ran.

## Scheduled runs

You can view all the runs in the [actions tab](https://github.com/ray-project/releaser/actions) and the test sessions themselves in Anyscale project page. If you are an Anyscale engineer, you can find the bot account information in shared 1Password vault.

The follow tests are ran periodically:

- Daily: microbenchmark, serve-microbenchmark
- Weekly (every Monday): serve cluster tests, rllib tests, pbt failure tests, long running tests.

## Running locally

To add a new test, just edit the `config.toml` file.

```
$ python cli.py --help
python cli.py --help
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

Options:
  --git-branch TEXT     [default: master]
  --git-commit TEXT
  --git-org TEXT        [default: ray-project]

$ python cli.py suite:run --help
Running precondition check...
💰 Checking out master
🧬 Latest commit (with wheels) is "abb1eefdc - Sven Mika, 2 hours ago: [RLlib] Issue 12483: Discrete observation space error: "ValueError: ('Observation ({}) outside given space ..." when doing Trainer.compute_action. (#12787)"
📖 Running with context: {'git_branch': 'master', 'git_commit': 'abb1eefdc23f197b7ea7a0e54363a56408a86c61', 'ray_version': '1.1.0.dev0'}
Usage: cli.py suite:run [OPTIONS] NAME

  Run a single test suite given `name`.

Arguments:
  NAME  [required]

Options:
  --dry-run / --no-dry-run  [default: False]
  --wait / --no-wait        [default: True]
  --stop / --no-stop        [default: True]
  --help                    Show this message and exit.

$ python cli.py suite:run microbenchmark

Running precondition check...
💰 Checking out master
🧬 Latest commit is "6426fb3ff - Ian Rodney, 81 minutes ago: [CI] Fix-Up Docker Build (Use Python) (#11139)"
📖 Running with context: {'git_branch': 'master', 'git_commit': '6426fb3fffe56878e26bf35d990a806cb4b3e97b', 'ray_version': '1.1.0.dev0'}
😃 Validation successful!
{...,
 'microbenchmark': {'base_dir': 'ci/microbenchmark',
                    'cluster_config': 'ray-project/cluster.yaml',
                    'exec_cmd': 'bash run.sh --ray-version=1.1.0.dev0 '
                                '--commit=6426fb3fffe56878e26bf35d990a806cb4b3e97b '
                                '--ray-branch=master'}}
🗺 Execution plan (within ci/microbenchmark)
        anyscale init --name release-automation-microbenchmark --config ray-project/cluster.yaml || echo 'Project already registered.'
        anyscale up --yes --config ray-project/cluster.yaml 1602542637
        anyscale exec --stop --session-name 1602542637 -- bash run.sh --ray-version=1.1.0.dev0 --commit=6426fb3fffe56878e26bf35d990a806cb4b3e97b --ray-branch=master 2>&1 | tee 1602542637.log

... execution log omitted
```

## Tips for adding a new release test

If you are iterating on a release test and wish to be able to change the `run.sh` or `config.yaml` file that
exists in the `ray` repository for a given file, you can change the file in the version of the `ray` repo that
the releaser tool clones to the `./ray` directory. This is useful because it removes the wait for a new
wheel build to complete that would be required if you made the change on your branch of the `ray` repository
and pushed it up.
