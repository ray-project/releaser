import os

from anyscale.credentials import load_credentials
from anyscale.sdk.anyscale_client.sdk import AnyscaleSDK
from dotenv import load_dotenv
from tabulate import tabulate
from typer import Typer

IGNORE_PROJECT_IDS = {"prj_6kvvLH0v8aGCdejtJlnwB7", "prj_2OKN03tMM2tqm6HX11txf"}

app = Typer()


@app.command("list")
def do_list(
    interactive: bool = True, verbose: bool = False, exclude_stopped: bool = True
):
    load_dotenv()
    if interactive:
        verbose = True
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
            resp = anyscale_sdk.list_sessions(
                proj.id, count=50, paging_token=paging_token
            )
            sessions.extend(resp.results)

            paging_token = resp.metadata.next_paging_token
            has_more = paging_token is not None

        for sess in sessions:
            ignore_states = {"Terminated"}
            if exclude_stopped:
                ignore_states.add("Stopped")
            if sess.state in ignore_states:
                continue

            table.append(
                [
                    (proj.id),
                    (proj.name),
                    (sess.id),
                    (sess.name),
                    (sess.state),
                    (sess.pending_state),
                ]
                if verbose
                else [
                    (proj.name),
                    (sess.name),
                    (sess.state),
                ]
            )

    print(
        tabulate(
            table,
            headers=[
                "proj.id",
                "proj.name",
                "sess.id",
                "sess.name",
                "sess.state",
                "sess.pending_state",
            ]
            if verbose
            else [
                "proj.name",
                "sess.name",
                "sess.state",
            ],
        )
    )

    if len(table) > 0 and interactive:
        response = input("Terminate sessions? [Y/n]").lower().strip()
        if response == "y":
            for _, _, sess_id, _, sess_state, *_ in table:
                if sess_state == "Terminating":
                    continue
                print("Terminating", sess_id)
                resp = anyscale_sdk.terminate_session(sess_id, {})
                print(resp)


if __name__ == "__main__":
    app()