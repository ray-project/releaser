# Releaser

Releaser is a command line tool that runs Ray release tests.

It helps running the release tests on managed ray. To add a new test, just edit the `config.toml` file.

```
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
        anyscale push --all-nodes
        anyscale exec --session-name 1602542637 -- bash run.sh --ray-version=1.1.0.dev0 --commit=6426fb3fffe56878e26bf35d990a806cb4b3e97b --ray-branch=master 2>&1 | tee 1602542637.log
        anyscale down --terminate 1602542637
        aws cp 1602542637.log s3://ray-travis-logs/periodic_tests/microbenchmark/1602542637.log

... execution log omitted
```
