import os

from anyscale.credentials import load_credentials
from anyscale.sdk.anyscale_client.sdk import AnyscaleSDK
from dotenv import load_dotenv
from tabulate import tabulate

IGNORE_PROJECT_IDS = {"prj_6kvvLH0v8aGCdejtJlnwB7"}

load_dotenv()
token = os.environ.get("ANYSCALE_CLI_TOKEN") or load_credentials()
anyscale_sdk = AnyscaleSDK(token)

all_projects = anyscale_sdk.search_projects({"paging": {"count": 100}}).results
table = []
for proj in all_projects:

    if not proj.name.startswith("release"):
        continue

    if proj.id in IGNORE_PROJECT_IDS:
        continue

    sessions = []
    has_more = True
    paging_token = None
    while has_more:
        resp = anyscale_sdk.list_sessions(proj.id, count=50, paging_token=paging_token)
        sessions.extend(resp.results)

        paging_token = resp.metadata.next_paging_token
        has_more = paging_token is not None

    for sess in sessions:
        if sess.state in {"Stopped", "Terminated"}:
            continue

        table.append(
            [
                (proj.id),
                (proj.name),
                (sess.id),
                (sess.name),
                (sess.state),
            ]
        )

print(
    tabulate(
        table, headers=["proj.id", "proj.name", "sess.id", "sess.name", "sess.state"]
    )
)

if len(table) > 0:
    response = input("Terminate sessions? [Y/n]").lower().strip()
    if response == "y":
        for proj_id, _, sess_id, _, _ in table:
            resp = anyscale_sdk.terminate_session(sess_id, {})
            print(resp)

