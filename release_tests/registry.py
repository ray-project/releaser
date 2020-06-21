from dataclasses import dataclass

from context import Context
from controller import TestController
from release_tests.microbenchmark.controller import MicrobenchmarkTestController

@dataclass
class ReleaseTestMetadata:
    name: str
    controller: TestController = None
    context: Context = None
    expected_duration_hours: int = None


# -- Release Test Types --
MICROBENCHMARK = "microbenchmark"


# -- Releae Test Config --
config = {
    MICROBENCHMARK: ReleaseTestMetadata(
        name=MICROBENCHMARK,
        controller=MicrobenchmarkTestController,
        context=None,
        expected_duration_hours=1
    )
}

release_tests = [
    release_test_name for release_test_name in config.keys()
]


def get_test_controller(context):
    release_test_metadata = config.get(context.test_type)
    assert release_test_metadata is not None, f"Test type: {test_type} doesnot exist."
    return release_test_metadata.controller(context)


def get_test_expected_uptime(test_type):
    return config[test_type].expected_duration_hours
