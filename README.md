# Releaser
Releaser is a command line tool that runs Ray release tests.

If you have any suggestion for improvement, please file a Github issue or DM @sang.

It consists of
- Commands to run release tests using Anyscale product.
- Main cron job that runs release tests based on the configuration specified in schedule.yaml.
- Supports updating results to Slack channels or private S3 buckets.

```bash
# Run microbenchmark
python releaser.py run microbenchmark
```

## How to Add New Tests
Adding new tests is the most important use case for releaser. Please follow the manual below to add new tests.

### Add a New Test
Releaser requires you to add APIs that are shared by both the command line tool and cron job.

Search NEW_TESTS - BASIC. It will give you a list of files that you should modify to support new tests.

#### release_tests/[test_name]/controller.py
You first need to create a controller.py. Controller is a class that has the core logic of each release tests. For example,

- Code to start a session and run tests.
- Code to create a log file to update S3 based on session logs.
- Code to write slack messages after session is done.

All methods that should be implemented is defined in `controller.TestController`. Inherit this class and override methods.
We will revisit how to actually write code for them later. Just write a structure with empty method body for now.

Look at `release_tests/microbenchmark/controller.py` as a reference.

First, create `__init__.py`
Second, create `controller.py`. Copy and paste code from `release_tests/microbenchmark/controller.py` and comment out function bodies.
Change the class name properly.

#### release_tests/registry.py
Now, we should register them to the test registry. You will need to define important metadata for each release tests.
Add a new metadata entry to `config` dictionary. Please refer to microbenchmark as an example.

__NOTE: The name of your test should be equivalent to release test name defined in CI.__

```python3
    MICROBENCHMARK: ReleaseTestMetadata(
        name=MICROBENCHMARK, # Name of the test. This must be the same as the folder name your controller.py is defined.
        path="microbenchmark", # Path to the release test folder inside ray/ci folder.
        controller=MicrobenchmarkTestController, # The controller you defined.
        context=None, # Not used for now. Just mark it None.
        expected_duration_hours=1 # The estimated hours this test should be running for. It is used to force-terminate sessions that are hanging.
    )
```

#### api.py
Now, it is time to add an API! These methods are shared by both command line tool and cron job, so it is a necessary step. 

Go to `api.py` and look at `run_microbenchmark` as an example. 

Note that here, inputs are flexible. You can add as many inputs as you want. If you don't have any specific requirement, just follow the microbenchmark example. If you want to provide more inputs than the default defined in `Context` object, you should create your custom Context. Guide for this is not written yet because there's no requirements yet.

### Add a command
Now, it is time to add a command! Search NEW_TESTS - CommandLine. It will lead you to the page that you need to add a new command.

Also, look at def microbenchmark example. Note that you can flexibly choose inputs here. Once you add them here, you are able to run tests using python releaser.py run [your_test_name].


### Write Controller Methods
It is now time to override controller methods. You need to override 3 methods to achieve the complete behavior.

`run`: Write the logic to run anyscale command to start release tests.
`process_logs`: Return the string that will be backed up to private S3 bucket. Note that the input will be the log output from the product.
`generate_slackbot_message`: Decide the slackabot message that will be posted. The input result will be equivalent to the return value of `process_logs`.


### Run it periodically
