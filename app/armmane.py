
import os
from loguru import logger

try:
    import conmane as cmn
except:
    from app import conmane as cmn

class AiMane:
    def __init__(self):
        self.app_path = "app"
        self.userdata_path = "userdata"
        self.config_path = os.path.join(self.app_path, "config")
        
        # CONFIG LOAD


        # Config will be {self.store_path}/config/config_name.json using join
        self.model_config = cmn.ConfigMane("model_config.json", self.config_path)
        self.running_config = cmn.ConfigMane("running_config.json", self.config_path)
        self.prediction_result = cmn.ConfigMane("prediction_result.json", self.config_path)


    if __name__ == "__main__":
        # Print Red Error Message
        print("[ERR] AImane is a library, please run the program from server.py file.")
        exit(0)
