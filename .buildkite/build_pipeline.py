import copy
import os
import sys
import yaml

NIGHTLY_TESTS = {
    "~/ray/release/microbenchmark/microbenchmark.yaml": [
        "microbenchmark",
    ],
    "~/ray/release/xgboost_tests/xgboost_tests.yaml": [
        "train_small",
        "train_moderate",
        "train_gpu",
        "tune_small",
        "tune_4x32",
        "tune_32x4",
        "ft_small_elastic",
        "ft_small_non_elastic",
        "distributed_api_test",
    ]
}

DEFAULT_STEP_TEMPLATE = {
    "env": {
        "ANYSCALE_CLOUD_ID": "cld_4F7k8814aZzGG8TNUGPKnc",
        "ANYSCALE_PROJECT": "prj_2xR6uT6t7jJuu1aCwWMsle",
        "RELEASE_AWS_BUCKET": "ray-release-automation-results",
        "RELEASE_AWS_LOCATION": "dev",
        "RELEASE_AWS_DB_NAME": "ray_ci",
        "RELEASE_AWS_DB_TABLE": "release_test_result",
        "AWS_REGION": "us-west-2"
    },
    "agents": {
        "queue": "runner_queue_branch"
    },
    "plugins": [
        {
            "docker#v3.8.0": {
                "image": "rayproject/ray",
                "propagate-environment": True
            }
        }
    ],
    "commands": []
}


def build_pipeline(steps):
    all_steps = []

    RAY_BRANCH = os.environ.get("RAY_BRANCH", "master")
    RAY_REPO = os.environ.get("RAY_REPO", "https://github.com/ray-project/ray.git")

    for test_file, test_names in steps.items():
        test_base = os.path.basename(test_file)
        for test_name in test_names:
            step_conf = copy.deepcopy(DEFAULT_STEP_TEMPLATE)

            cmd = str(f"python e2e.py "
                      f"--ray-branch {RAY_BRANCH} "
                      f"--category {RAY_BRANCH} "
                      f"--test-config {test_file} "
                      f"--test-name {test_name}")

            step_conf["commands"] = [
                "pip install -q -r requirements.txt",
                "pip install -U boto3 botocore",
                f"git clone -b {RAY_BRANCH} {RAY_REPO} ~/ray",
                cmd,
            ]

            step_conf["label"] = f"({RAY_BRANCH}) {test_base}: {test_name}"
            all_steps.append(step_conf)

    return all_steps


if __name__ == "__main__":
    steps = build_pipeline(NIGHTLY_TESTS)

    yaml.dump({"steps": steps}, sys.stdout)
