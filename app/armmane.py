import os
from loguru import logger


from app import sysmane as smn
import threading


class ArmMane:  
    def __init__(self,sysmane,serimane):
        self.sysm = sysmane
        self.seri = serimane


        self.status = {
            "step": 0,
            "idle" : True,
            "start" : 0,
            "mode" : 1
        }


    def setMode(self,mode):
        if(mode == "auto"):
            if(self.status["mode"] == 1):
                logger.warning("Already in auto mode")
            else:
                self.status["mode"] = 1
                self.startAuto()

        
        elif(mode == "manual"):
            self.status["mode"] = 0
        else:
            logger.error("Invalid mode")
            return False
        return True
    


    def startAuto(self):
        # Start step control thread
        logger.debug("Start auto mode")
        # Start the thread
        threading.Thread(target=self.autoMane).start()


    # def autoMane(self):
    #     # Check current step




    # def stepControl(self,step):
    #     #Step 0: Reset the arm to the initial position
    #     # foreach the automatic_step of step0 in config
    #     #   send the instruction to the serial

    #     for step in self.sysm.config["automatic_step"]["step0"]:
    #         self.seri.piInstruction(step)
    #         logger.debug(f"Step0: {step}")