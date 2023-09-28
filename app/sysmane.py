import os
import json 

from loguru import logger
try:
    #import TFmane as tfm
    import conmane as cmn
except:
    #from app import TFmane as tfm
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
            "current_result": None,
            "confident_score" : 0,
            "current_classes" : "",
            "detect_flag" : False,
            "fps" : 0
        }

    def getConfig(self):
        return self.app_config
    
    def reloadConfig(self):
        self.app_config.reload()
        logger.info("Reload user config")
    
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
        return os.path.join(self.app_config.get("model_folder"), model_name, self.getModelConfig(model_name).get("model_file"))
    
    def getFullModelPath(self, model_name):
        return os.path.join(self.current_path, self.getModelPath(model_name))
    
    def setCurrentFrame(self, frame):
        self.running["current_frame"] = frame

    def getCurrentFrame(self):
        return self.running["current_frame"]
    
    def setCurrentResultFrame(self, result):
        self.running["current_result"] = result
    
    def getCurrentFrame(self):
        return self.running["current_result"]

    def setCurrentResult(self,confident_score, classes, fps, flag):
        self.running["current_confident_score"] = confident_score
        self.running["current_classes"] = classes
        self.running["fps"] = fps
        self.running["detect_flag"] = flag
    
    def getCurrentResult(self):
        return self.running

    def setCurrentResult(self, result):
        self.running = result

    

