from dataclasses import dataclass

from pathlib import Path

import constant

from release_tests import registry


class ConfigManager:
    def __init__(self, config_file_path: str = constant.CONFIG_FILE):
        self.config_file_path = config_file_path
        # Line by line definition
        self._config_def_by_lines = [
            "ray_path",
        ]
        self._config = {
            config_def: None 
            for config_def in self._config_def_by_lines
        }

    @property
    def release_test_dir(self):
        return Path("{}/{}".format(self._config["ray_path"], "ci"))

    @property
    def config_exists(self):
        return Path(self.config_file_path).exists()

    def config_update_if_needed(self, ray_path: str = None):
        config_dir = Path(constant.TEMP_DIR)
        config_dir.mkdir(exist_ok=True)
        if not self.config_exists:
            self._create_config_file(ray_path)
        self._read_config()

    def _create_config_file(self, ray_path):
        if not ray_path:
            ray_path = input("Specify the absolute path to the ray repo: ")
        ray_dir = Path(ray_path)
        if not ray_dir.is_absolute():
            raise ValueError("Only absolute path is allowed.")
        if not ray_dir.exists():
            raise ValueError("Ray directory path {} doesn't exist.".format(ray_dir))
        if ray_path.endswith("/"):
            # strip / at the end.
            ray_path = ray_path[:-1]

        self._config["ray_path"] = ray_path
        self._write_config()

    def _write_config(self):
        with open(self.config_file_path, "a") as f:
            for config_def in self._config_def_by_lines:
                f.write("{}\n".format(self._config[config_def]))

    def _read_config(self):
        with open(self.config_file_path, "r") as f:
            from pprint import pprint
            for i, line in enumerate(f.readline().strip("\n").split("\n")):
                self._config[self._config_def_by_lines[i]] = line.strip("\n")


global_config_manager = ConfigManager()

def get_test_dir(test_type: str) -> str:
    return (global_config_manager.release_test_dir 
            / registry.get_release_test_path(test_type))
