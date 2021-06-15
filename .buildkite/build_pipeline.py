import copy
import logging
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
    ],
    "~/ray/release/tune_tests/scalability_tests/tune_tests.yaml": [
        "bookkeeping_overhead",
        "network_overhead",
        "result_throughput_cluster",
        "result_throughput_single_node",
        "xgboost_sweep",
    ],
    "~/ray/release/nightly_tests/nightly_tests.yaml": [
        "shuffle_10gb", "shuffle_50gb", "shuffle_50gb_large_partition",
        "shuffle_100gb", "non_streaming_shuffle_100gb",
        "non_streaming_shuffle_50gb_large_partition",
        "non_streaming_shuffle_50gb", "dask_on_ray_10gb_sort",
        "dask_on_ray_100gb_sort", "shuffle_1tb_large_partition",
        "dask_on_ray_large_scale_test_no_spilling",
        "dask_on_ray_large_scale_test_spilling"
    ],
    "~/ray/release/nightly_gpu_tests/nightly_gpu_tests.yaml": [
        "sgd_gpu",
    ],
}

MANUAL_TESTS = {
    "~/ray/release/tune_tests/scalability_tests/tune_tests.yaml": [
        "durable_trainable",
        "long_running_large_checkpoints",
    ],
    "~/ray/release/long_running_tests/scalability_tests/tune_tests.yaml": [
        "actor_deaths",
        "apex",
        "impala",
        "many_actor_tasks",
        "many_drivers",
        "many_ppo",
        "many_tasks",
        "many_tasks_serialized_ids",
        "node_failures",
        # "object_spilling_shuffle",
        "pbt",
        # "serve",
        "serve_failure",
    ],
}

SUITES = {
    "nightly": NIGHTLY_TESTS,
    "manual": MANUAL_TESTS,
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
    "plugins": [{
        "docker#v3.8.0": {
            "image": "rayproject/ray",
            "propagate-environment": True
        }
    }],
    "commands": []
}


def build_pipeline(steps):
    all_steps = []

    RAY_BRANCH = os.environ.get("RAY_BRANCH", "master")
    RAY_REPO = os.environ.get("RAY_REPO",
                              "https://github.com/ray-project/ray.git")

    RAY_TEST_BRANCH = os.environ.get("RAY_TEST_BRANCH", RAY_BRANCH)
    RAY_TEST_REPO = os.environ.get("RAY_TEST_REPO", RAY_REPO)

    FILTER_FILE = os.environ.get("FILTER_FILE", "")
    FILTER_TEST = os.environ.get("FILTER_TEST", "")

    logging.info(
        f"Building pipeline \n"
        f"Ray repo/branch to test:\n"
        f" RAY_REPO   = {RAY_REPO}\n"
        f" RAY_BRANCH = {RAY_BRANCH}\n\n"
        f"Ray repo/branch containing the test configurations and scripts:"
        f" RAY_TEST_REPO   = {RAY_TEST_REPO}\n"
        f" RAY_TEST_BRANCH = {RAY_TEST_BRANCH}\n\n"
        f"Filtering for these tests:\n"
        f" FILTER_FILE = {FILTER_FILE}\n"
        f" FILTER_TEST = {FILTER_TEST}\n\n")

    for test_file, test_names in steps.items():
        if FILTER_FILE and FILTER_FILE not in test_file:
            continue

        test_base = os.path.basename(test_file)
        for test_name in test_names:
            if FILTER_TEST and FILTER_TEST not in test_name:
                continue

            logging.info(f"Adding test: {test_base}/{test_name}")

            step_conf = copy.deepcopy(DEFAULT_STEP_TEMPLATE)

            cmd = str(f"python e2e.py "
                      f"--ray-branch {RAY_BRANCH} "
                      f"--category {RAY_BRANCH} "
                      f"--test-config {test_file} "
                      f"--test-name {test_name}")

            step_conf["commands"] = [
                "pip install -q -r requirements.txt",
                "pip install -U boto3 botocore",
                f"git clone -b {RAY_TEST_BRANCH} {RAY_TEST_REPO} ~/ray",
                cmd,
            ]

            step_conf["label"] = f"({RAY_BRANCH}) " \
                                 f"{RAY_TEST_BRANCH}/{test_base}: {test_name}"
            all_steps.append(step_conf)

    return all_steps


if __name__ == "__main__":
    TEST_SUITE = os.environ.get("RELEASE_TEST_SUITE", "nightly")
    PIPELINE_SPEC = SUITES[TEST_SUITE]

    steps = build_pipeline(PIPELINE_SPEC)

    yaml.dump({"steps": steps}, sys.stdout)
