import json

from typing import List, Dict

from pydantic import BaseModel

from release_tests import registry
from util import run_subprocess, get_test_dir, cd

class CommandState(BaseModel):
    created_at: str
    name: str
    params: Dict[str, str]
    session_command_id: int
    status: str


class SessionState(BaseModel):
    commands: List[CommandState]
    created_at: str
    name: str
    status: str


class Scanner:
    """Class to scan project and detect running tests."""

    def __init__(self, test_type: str):
        self.test_type = test_type
    
    def get_completed_sessions(self) -> List[str]:
        session_info_list: List[SessionState] = self._get_all_session_info()
        return [
            session_state.name
                for session_state in session_info_list
                if self._is_session_completed(session_state)
            ]

    def get_old_sessions(self) -> List[str]:
        session_info_list: List[SessionState] = self._get_all_session_info()
        return [
            session_state.name
                for session_state in session_info_list
                if self._is_session_old(session_state)
        ]

    def _get_all_session_info(self) -> List[SessionState]:
        output = None
        session_info_list = []
        with cd(get_test_dir(self.test_type)):
            command = ["anyscale", "list", "sessions", "--json"]
            output, _, _ = run_subprocess(
                command,
                print_output=False
            )
            assert output is not None, (
                f"Didn't get output from {' '.join(command)}")

            # Parse session information.
            for session_info in json.loads(output.replace("'", "\"")):
                session_info_list.append(SessionState.parse_obj(session_info))
        return session_info_list

    def _is_session_completed(self, session_state: SessionState):
        """Return True if the given session state is completed"""
        if len(session_state.commands) == 0:
            return False
        
        return all([
            command.status == "FINISHED"
                for command in session_state.commands
            ])
        
    def _is_session_old(self, session_state: SessionState):
        """Return True if the given session lasts more than 8 hours"""
        uptime_hours = self._parse_time_from_command(session_state.created_at)
        return uptime_hours > registry.get_test_expected_uptime(self.test_type)

    def _parse_time_from_command(self, created_at: str):
        # NOTE: This is tightly coupled to anyscale command.
        # Example created_at value: 1 minute ago.
        unit, measure, _ = created_at.split(" ")
        unit = int(unit)
        if measure.startswith("seconds"):
            return unit / 3600
        elif measure.startswith("minute"):
            return unit / 60
        elif measure.startswith("hour"):
            return unit
        elif measure.startswith("day"):
            return 24 * unit
        else:
            raise Exception(f"Unknown time measure {measure} is given.")
