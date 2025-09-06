import json
import os
from pathlib import Path

from src.Logger.LoggerClass import Logger

class ConfigManager:
    def __init__(self):
        self.settings_path: Path = self._find_config()
        self._settings = self._get_settings()
        
    def _find_config(self) -> Path:
        possible_path = [
            "settings.json"
        ]
        
        for path in possible_path:
            tmp = Path(path)
            if tmp.exists() and tmp.is_file():
                return tmp

        Logger.fatal("Failed to find settings.json file")
        # Should be raised by the Logger.fatal
        raise FileNotFoundError("Failed to find settings.json file")
    
    def _get_settings(self):
        try:
            with open(self.settings_path, 'r') as f:
                return json.load(f)

        except json.JSONDecodeError as e:
            Logger.fatal(f"Invalid JSON in config file: {e}")
            # Should be raised by the Logger.fatal
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            Logger.fatal(f"Error reading config file: {e}")
            # Should be raised by the Logger.fatal
            raise Exception(f"Error reading config file: {e}")

    def get(self, key: str, default_value = None):
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                if (default_value):
                    return default_value
                else:
                    Logger.error(f"The key: {k} ({keys}) was not found!")

        return value

    def refresh_config(self):
        self._settings = self._get_settings()