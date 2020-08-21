from dataclasses import dataclass

from context import Context
from controller import TestController
from release_tests.microbenchmark.controller import MicrobenchmarkTestController
from release_tests.long_running_tests.controller import LongRunningTestsController
from release_tests.long_running_distributed_tests.controller import LongRunningDistributedTestsController
from release_tests.rllib_tests.regression_tests.controller import RLlibRegressionTestController
from release_tests.rllib_tests.unit_gpu_tests.controller import RLlibUnitGPUTestController
from release_tests.stress_tests.controller import StressTestController

@dataclass
class ReleaseTestMetadata:
    name: str
    # Path from ci/... For example, stress_tests should have a path
    # regression_test/stress_tests
    path: str
    controller: TestController = None
    context: Context = None
    expected_duration_hours: int = None


# -- Release Test Types --
# NEW_TESTS - BASIC
MICROBENCHMARK = "microbenchmark"
STRESS_TESTS = "stress_tests"
LONG_RUNNING_TESTS = "long_running_tests"
LONG_RUNNING_DISTRIBUTED_TESTS = "long_running_distributed_tests"
RLLIB_REGRESSION_TESTS = "rllib_regression_tests"
RLLIB_UNIT_GPU_TESTS = "rllib_unit_gpu_tests"


# -- Releae Test Config --
# NEW_TESTS - BASIC
config = {
    MICROBENCHMARK: ReleaseTestMetadata(
        name=MICROBENCHMARK,
        path="microbenchmark",
        controller=MicrobenchmarkTestController,
        context=None,
        expected_duration_hours=1
    ),
    LONG_RUNNING_TESTS: ReleaseTestMetadata(
        name=LONG_RUNNING_TESTS,
        path="long_running_tests",
        controller=LongRunningTestsController,
        context=None,
        expected_duration_hours=1
    ),
    LONG_RUNNING_DISTRIBUTED_TESTS: ReleaseTestMetadata(
        name=LONG_RUNNING_DISTRIBUTED_TESTS,
        path="long_running_distributed_tests",
        controller=LongRunningDistributedTestsController,
        context=None,
        expected_duration_hours=1
    ),
    RLLIB_REGRESSION_TESTS: ReleaseTestMetadata(
        name=RLLIB_REGRESSION_TESTS,
        path="rllib_tests/regression_tests",
        controller=RLlibRegressionTestController,
        context=None,
        expected_duration_hours=4
    ),
    RLLIB_UNIT_GPU_TESTS: ReleaseTestMetadata(
        name=RLLIB_UNIT_GPU_TESTS,
        path="rllib_tests/unit_gpu_tests",
        controller=RLlibUnitGPUTestController,
        context=None,
        expected_duration_hours=2
    ),
    STRESS_TESTS: ReleaseTestMetadata(
        name=STRESS_TESTS,
        path="stress_tests",
        controller=StressTestController,
        context=None,
        expected_duration_hours=1
    ),
}

# -- Workloads --
STRESS_TESTS_WORKLOADS = [
    "test_dead_actors",
    "test_many_tasks",
]
LONG_RUNNING_TESTS_WORKLOADS = [
    "actor_deaths",
    "apex",
    "impala",
    "many_actor_tasks",
    "many_drivers",
    "many_tasks",
    "node_failures",
    "pbt",
    "serve",
    "serve_failure",
    "many_tasks_serialized_ids",
]
LONG_RUNNING_DISTRIBUTED_TESTS_WORKLOADS = [
    "pytorch_pbt_failure"
]

# -- Aggregated configs --
release_tests = [
    release_test_name for release_test_name in config.keys()
]

release_tests_path = {
    metdata.name: metdata.path for metdata in config.values()
}


def get_test_controller(context):
    release_test_metadata = config.get(context.test_type)
    assert release_test_metadata is not None, f"Test type: {test_type} doesnot exist."
    return release_test_metadata.controller(context)


def get_test_expected_uptime(test_type):
    return config[test_type].expected_duration_hours


def get_release_test_path(test_type):
    return release_tests_path[test_type]
