from typing import Dict, Any
import datetime
import hashlib
import json
import logging
import sys

import boto3

from e2e import GLOBAL_CONFIG

from alerts.tune_tests import handle_result as tune_tests_handle_result

SUITE_TO_FN = {
    "tune_tests": tune_tests_handle_result,
}


logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(fmt="[%(levelname)s %(asctime)s] "
                              "%(filename)s: %(lineno)d  "
                              "%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def _obj_hash(obj: Any) -> str:
    json_str = json.dumps(obj, sort_keys=True, ensure_ascii=True)
    sha = hashlib.sha256()
    sha.update(json_str.encode())
    return sha.hexdigest()


def fetch_latest_alerts():
    pass


def fetch_latest_results():
    rds_data_client = boto3.client("rds-data", region_name="us-west-2")

    schema = GLOBAL_CONFIG["RELEASE_AWS_DB_TABLE"]

    sql = (f"""
        SELECT DISTINCT ON (category, test_suite, test_name)
               created_on, category, test_suite, test_name, status, results, artifacts, last_logs
        FROM   {schema}
        ORDER BY category, test_suite, test_name, created_on DESC
        """)

    result = rds_data_client.execute_statement(
        database=GLOBAL_CONFIG["RELEASE_AWS_DB_NAME"],
        secretArn=GLOBAL_CONFIG["RELEASE_AWS_DB_SECRET_ARN"],
        resourceArn=GLOBAL_CONFIG["RELEASE_AWS_DB_RESOURCE_ARN"],
        schema=schema,
        sql=sql,
    )
    for row in result["records"]:
        created_on, category, test_suite, test_name, status, results, artifacts, last_logs = (
            r["stringValue"] if "stringValue" in r else None for r in row)

        # Calculate hash before converting strings to objects
        result_obj = (created_on, category, test_suite, test_name, status, results, artifacts, last_logs)
        result_json = json.dumps(result_obj)
        result_hash = _obj_hash(result_json)

        # Convert some strings to python objects
        created_on = datetime.datetime.strptime(created_on,
                                                "%Y-%m-%d %H:%M:%S")
        results = json.loads(results)
        artifacts = json.loads(artifacts)

        print(category, test_suite, test_name, result_hash)

        # Todo: Find out if result should be handled (by hashing etc)
        handle_fn = SUITE_TO_FN.get(test_suite, None)
        if not handle_fn:
            logger.warning(f"No handle for suite {test_suite}")
            continue

        alert = handle_fn(
            created_on, category, test_suite, test_name, status, results,
            artifacts, last_logs)

        if alert:
            print(f"ALERT! {alert}")
        else:
            logger.debug(
                f"No alert raised for test {test_suite}/{test_name} "
                f"({category})")

        # Todo: mark


if __name__ == "__main__":
    fetch_latest_results()
