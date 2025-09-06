import json
import os
from pathlib import Path

from src.Logger.LoggerClass import Logger

class ConfigManager:
    __possible_path = [
        "settings.json"
    ]
    
    @staticmethod
    def __find_config() -> Path:
        for path in ConfigManager.__possible_path:
            tmp = Path(path)
            if tmp.exists() and tmp.is_file():
                return tmp

        Logger.fatal("Failed to find settings.json file")
        # Should be raised by the Logger.fatal
        raise FileNotFoundError("Failed to find settings.json file")
    
    @staticmethod
    def __get_settings(settings_path: Path):
        try:
            with open(settings_path, 'r') as f:
                return json.load(f)

        except json.JSONDecodeError as e:
            Logger.fatal(f"Invalid JSON in config file: {e}")
            # Should be raised by the Logger.fatal
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            Logger.fatal(f"Error reading config file: {e}")
            # Should be raised by the Logger.fatal
            raise Exception(f"Error reading config file: {e}")

    @staticmethod
    def get_all_settings():
        """Will return all the config in a JSON object

        Returns:
            any: The config in a JSON object
        """
        return ConfigManager.__get_settings(ConfigManager.__find_config())

    @staticmethod
    def get(key: str, default_value = None):
        """Will return the value held by the key. This is a "hot-reload", 
        meaning that it will check each time this function is called for
        changes.

        Args:
            key (str): The key, should be separated by commas (e.g: var.to.get)
            default_value (any, optional): Default value if not found, 
                                              if None, will send a log Error. 
                                              Defaults to None.

        Returns:
            any: The value of the key
        """
        
        # TODO: For now, handles simple stuff (lists not included)
        
        keys = key.split('.')
        value = ConfigManager.get_all_settings()
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                if (default_value):
                    return default_value
                else:
                    Logger.error(f"The key: {k} ({keys}) was not found!")
                    return None

        return value
    
    @staticmethod
    def set(key: str, value):
        
        # TODO: For now, handles simple stuff (lists not included)
        
        keys = key.split('.')
        cur = ConfigManager.get_all_settings()
        
        for k in keys[:-1]:
            if not isinstance(cur, dict) or k in cur:
                cur[k] = {}
            cur = cur[k]
            
        cur[keys[-1]] = value