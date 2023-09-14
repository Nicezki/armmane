import os
import json
from loguru import logger

class ConfigMane:
    def __init__(self, config_file_name, config_path=None):
        self.config_path = config_path or os.path.join(os.getcwd(), 'store')
        self.config_file = os.path.join(self.config_path, config_file_name)
        self.config = {}
        self.loadConfig()

    def loadConfig(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"Config file '{self.config_file}' not found.")
            self.config = {}

    def saveConfig(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, *args):
        if not args:
            return self.config

        current_level = self.config

        for key in args:
            if key in current_level:
                current_level = current_level[key]
            else:
                logger.error(f"Key '{key}' not found in config.")
                return None

        return current_level
    

    def getAll(self):
        return self.config
    

    def change(self, key, value):
        self.config[key] = value

    def add(self, key, value):
        if key not in self.config:
            self.config[key] = value
        else:
            print(f"Key '{key}' already exists in the config.")

    def remove(self, key):
        if key in self.config:
            del self.config[key]
        else:
            print(f"Key '{key}' not found in the config.")

    def delete(self):
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
            self.config = {}
            print("Config file deleted.")
        else:
            print("Config file does not exist.")

    def reload(self):
        self.load_config()
        print("Config reloaded.")




    # def loadDataSet():
    #     try:
    #         with open(self.dataSet, 'r') as file:
    #             # Read the lines of the file, remove newline characters, and store them in an array
    #             file_contents = [line.strip() for line in file]
    #         return file_contents
    #     except FileNotFoundError:
    #         print(f"File '{self.filename}' not found.")
    #         return []

    # def get_value(self, index=None):
    #     if index is None:
    #         return self.file_contents
    #     elif isinstance(index, int) and 0 <= index < len(self.file_contents):
    #         return self.file_contents[index]
    #     else:
    #         print("Invalid index.")
    #         return None
        

