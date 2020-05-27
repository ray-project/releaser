import os

from subprocess import Popen, PIPE

class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, path):
        self.path = os.path.expanduser(path)

    def __enter__(self):
        self.saved_path = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.saved_path)


def run_subprocess(command: list, print_output: bool = True):
    unflattened_command = ' '.join(command)
    if print_output:
        print(f"\n=====Command Running=====\n{unflattened_command}")
    process = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    if print_output:
        print("\n=======Live Output======")
    while print_output:
        output = process.stdout.readline()
        if output == b'' and process.poll() is not None:
            break
        if output:
            print(output.decode().strip())

    if print_output:
        print("\n\n=========Done=======")
    output, error = process.communicate()

    output = output.decode().strip()
    error = error.decode().strip()
    return_code = process.returncode
    if print_output:
        print(f"Return Code: {str(return_code)}".strip())
        print(f"Error\n{error}".strip())
    return output, error, return_code


def parse_cluster_status(output, session_name):
    # This function is temporary.
    entries = output.split("\n")
    table_head_index = None
    for i, entry in enumerate(entries):
        entry = entries[i]
        if entry.strip().startswith("ACTIVE"):
            table_head_index = i

    if not table_head_index:
        raise Exception(
            "Failed to parse table head properly. "
            "It is mostly because `anyscale list sessions --all` "
            "output table format has been changed. Please rewrite "
            "the parsing logic at parse_cluster_status util function."
        )
    # At least table head and one session should exist in entries.
    assert len(entries) >= 2
    entries = entries[table_head_index:]
    table_head = entries[0]
    table_rows = entries[1:]
    # This is hacky because each table row is returned as a string.
    # We use the fact that each components will be always aligned with
    # the table head components. For example, if STATUS head starts from an index
    # 3, table row for STATUS will also starts from 3.
    status_start_index = table_head.find("STATUS")
    session_start_index = table_head.find("SESSION")
    created_start_index = table_head.find("CREATED")

    for entry in table_rows:
        active = entry[0].strip()
        status = entry[status_start_index:session_start_index].strip(' ')
        session_name_from_entry = entry[session_start_index:created_start_index].strip(' ')
        if session_name_from_entry == session_name:
            if status == "None":
                status = None
            active = True if active == "Y" else False
            return active, status
    assert False, (
        f"We could not find the session name {session_name} "
        "from from anyscale list sessions --all output. Please make sure"
        "You specified the correct session name that is in the project."
    )
