import os
import json 

from loguru import logger
try:
    # import TFmane as tfm
    import conmane as cmn
except:
    # from app import TFmane as tfm
    from app import conmane as cmn

class SysMane:
    def __init__(self):
        self.app_path = "app"
        self.userdata_path = "userdata"
        self.config_path = os.path.join(self.userdata_path, "config")
        self.current_path = os.getcwd()
        self.app_config = cmn.ConfigMane("config.json", self.config_path)
        self.current_model = self.app_config.get("current_model")
        self.running = {
            "current_frame": None,
        }

    def getConfig(self):
        return self.app_config
    
    def getCurrentModel(self):
        return self.current_model
    
    def getCurrentModelConfig(self):
        return self.getModelConfig(self.current_model)
    
    def getCurrentPath(self):
        return self.current_path
    
    def setCurrentModel(self, model_name):
        self.current_model = model_name
        self.app_config.change("current_model", model_name)
        self.app_config.save_config()

    def listModelFolder(self):
        logger.info("List model folder: {}".format(self.app_config.get("model_folder")))
        model_folder = os.path.join(self.app_config.get("model_folder"))
        return os.listdir(model_folder)
    
    def getModelConfig(self, model_name):
        model_folder = os.path.join(self.app_config.get("model_folder"), model_name)
        return cmn.ConfigMane("config.json", os.path.join(model_folder))
    
    def getModelPath(self,model_name):
        return os.path.join(self.app_config.get("model_folder"), model_name, self.getCurrentModelConfig().get("model_file"))
    
    def setCurrentFrame(self, frame):
        self.running["current_frame"] = frame

    def getCurrentFrame(self):
        return self.running["current_frame"]

    

