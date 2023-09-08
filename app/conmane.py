import os
import json

class ConfigMane:
    def __init__(self, config_file_name, config_path=None):
        self.config_path = config_path or os.path.join(os.getcwd(), 'store')
        self.config_file = os.path.join(self.config_path, config_file_name)
        self.config = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"Config file '{self.config_file}' not found.")
            self.config = {}

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key):
        return self.config.get(key)

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