from typing import Any
import datetime
import hashlib
import json
import logging
import os
import requests
import sys

import boto3

from e2e import GLOBAL_CONFIG

from alerts.tune_tests import handle_result as tune_tests_handle_result

SUITE_TO_FN = {
    "tune_tests": tune_tests_handle_result,
}

GLOBAL_CONFIG["RELEASE_AWS_DB_STATE_TABLE"] = "alert_state"
GLOBAL_CONFIG["SLACK_WEBHOOK"] = os.environ.get("SLACK_WEBHOOK")
GLOBAL_CONFIG["SLACK_CHANNEL"] = os.environ.get("SLACK_CHANNEL", "#kai-bot-test")

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


def fetch_latest_alerts(rds_data_client):
    schema = GLOBAL_CONFIG["RELEASE_AWS_DB_STATE_TABLE"]

    sql = (f"""
        SELECT DISTINCT ON (category, test_suite, test_name)
               category, test_suite, test_name, last_result_hash, last_notification_dt
        FROM   {schema}
        ORDER BY category, test_suite, test_name, last_notification_dt DESC
        """)

    result = rds_data_client.execute_statement(
        database=GLOBAL_CONFIG["RELEASE_AWS_DB_NAME"],
        secretArn=GLOBAL_CONFIG["RELEASE_AWS_DB_SECRET_ARN"],
        resourceArn=GLOBAL_CONFIG["RELEASE_AWS_DB_RESOURCE_ARN"],
        schema=schema,
        sql=sql,
    )
    for row in result["records"]:
        category, test_suite, test_name, last_result_hash, last_notification_dt = (
            r["stringValue"] if "stringValue" in r else None for r in row)
        last_notification_dt = datetime.datetime.strptime(
            last_notification_dt, "%Y-%m-%d %H:%M:%S")
        yield category, test_suite, test_name, last_result_hash, last_notification_dt


def fetch_latest_results(rds_data_client):
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
        result_obj = (created_on, category, test_suite, test_name, status,
                      results, artifacts, last_logs)
        result_json = json.dumps(result_obj)
        result_hash = _obj_hash(result_json)

        # Convert some strings to python objects
        created_on = datetime.datetime.strptime(created_on,
                                                "%Y-%m-%d %H:%M:%S")
        results = json.loads(results)
        artifacts = json.loads(artifacts)

        yield result_hash, created_on, category, test_suite, test_name, status, results, artifacts, last_logs


def mark_as_handled(
        rds_data_client,
        update: bool,
        category: str,
        test_suite: str,
        test_name: str,
        result_hash: str,
        last_notification_dt: datetime.datetime):
    schema = GLOBAL_CONFIG["RELEASE_AWS_DB_STATE_TABLE"]

    if not update:
        sql = (f"""
            INSERT INTO {schema}
            (category, test_suite, test_name, last_result_hash, last_notification_dt)
            VALUES (:category, :test_suite, :test_name, :last_result_hash, :last_notification_dt)  
            """)
    else:
        sql = (f"""
            UPDATE {schema}
            SET last_result_hash=:last_result_hash, last_notification_dt=:last_notification_dt
            WHERE category=:category AND test_suite=:test_suite AND test_name=:test_name
            """)

    rds_data_client.execute_statement(
        database=GLOBAL_CONFIG["RELEASE_AWS_DB_NAME"],
        parameters=[
            {
                "name": "category",
                "value": {
                    "stringValue": category
                }
            },
            {
                "name": "test_suite",
                "value": {
                    "stringValue": test_suite
                }
            },
            {
                "name": "test_name",
                "value": {
                    "stringValue": test_name
                }
            },
            {
                "name": "last_result_hash",
                "value": {
                    "stringValue": result_hash
                }
            },
            {
                "name": "last_notification_dt",
                "typeHint": "TIMESTAMP",
                "value": {
                    "stringValue": last_notification_dt.strftime(
                        "%Y-%m-%d %H:%M:%S")
                },
            },
        ],
        secretArn=GLOBAL_CONFIG["RELEASE_AWS_DB_SECRET_ARN"],
        resourceArn=GLOBAL_CONFIG["RELEASE_AWS_DB_RESOURCE_ARN"],
        schema=schema,
        sql=sql,
    )


def post_alert_to_slack(
    channel: str,
    alert: str
):
    print(f"POSTING ALERT TO SLACK {channel}: {alert}")
    return
    markdown_lines = [alert]
    slack_url = GLOBAL_CONFIG["SLACK_WEBHOOK"]

    resp = requests.post(
        slack_url,
        json={
            "text": "\n".join(markdown_lines),
            "channel": channel,
            "username": "Fail Bot",
            "icon_emoji": ":red_circle:",
        },
    )
    print(resp.status_code)
    print(resp.text)


def handle_results_and_send_alerts(rds_data_client):
    # First build a map of last notifications
    last_notifications_map = {}
    for category, test_suite, test_name, last_result_hash, \
            last_notification_dt in fetch_latest_alerts(rds_data_client):
        last_notifications_map[(category, test_suite,
                                test_name)] = (last_result_hash,
                                               last_notification_dt)

    # Then fetch latest results
    for result_hash, created_on, category, test_suite, test_name, status, \
            results, artifacts, last_logs in fetch_latest_results(rds_data_client):
        key = (category, test_suite, test_name)

        try_alert = False
        if key in last_notifications_map:
            # If we have an alert for this key, fetch info
            last_result_hash, last_notification_dt = last_notifications_map[
                key]

            if last_result_hash != result_hash:
                # If we got a new result, handle new result
                try_alert = True
            # Todo: maybe alert again after some time?
        else:
            try_alert = True

        if try_alert:
            handle_fn = SUITE_TO_FN.get(test_suite, None)
            if not handle_fn:
                logger.warning(f"No handle for suite {test_suite}")
                continue

            alert = handle_fn(created_on, category, test_suite, test_name,
                              status, results, artifacts, last_logs)

            if alert:
                print(f"ALERT! {alert}")
                post_alert_to_slack(
                    GLOBAL_CONFIG["SLACK_CHANNEL"],
                    alert)
            else:
                logger.debug(
                    f"No alert raised for test {test_suite}/{test_name} "
                    f"({category})")

            mark_as_handled(rds_data_client, key in last_notifications_map,
                            category, test_suite, test_name, result_hash,
                            datetime.datetime.now())


if __name__ == "__main__":
    rds_data_client = boto3.client("rds-data", region_name="us-west-2")

    handle_results_and_send_alerts(rds_data_client)
