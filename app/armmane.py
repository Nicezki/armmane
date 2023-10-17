import os
from loguru import logger

from app import sysmane as smn
import threading
import time


class ArmMane:  
    def __init__(self,sysmane,serimane,TFmane):
        self.sysm = sysmane
        self.seri = serimane
        self.tfma = TFmane

        self.status = {
            "step": 0,
            "idle" : True,
            "start" : 0,
            "mode" : 0,
            "items": [
                2,2,2,
            ]
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

    def stopAuto(self):
        logger.debug("Stop auto mode")
        self.status["mode"] = 0
        # Stop the thread
        if(threading.Thread(target=self.autoMane).is_alive()):
            logger.debug("Auto mode thread is alive, stop it")
            threading.Thread(target=self.autoMane).kill()
        else:
            logger.debug("Auto mode thread is not alive, do nothing")
            return
    
    def autoMane(self):
        # Check items in the box 
        # check every array in the items
        # if the item is 0 skip

        #Check the current step\
        while(self.status["mode"] == 1):
            current_step = self.status["step"]
            logger.debug(f"Current step is {current_step}")

            # Run the step
            self.runStep(current_step)

            if(current_step <5):
                self.status["step"] += 1
            else:
                self.status["step"] = 1
            logger.debug(f"Proceed to step {self.status['step']}")

            # Check if the mode is still auto
            if(self.status["mode"] == 0):
                logger.debug("Mode changed to manual, stop auto mode")
                # Stop the auto mode and kill the thread
                return
            
            # Check if seriak still avaliable
            
            # Wait for the next step
            time.sleep(0.1)
        logger.debug("Mode changed to manual, stop auto mode")
        # Stop the auto mode and kill the thread
        return
    

    def stepControl(self,current_step):
        #Step 0: Reset the arm to the initial position
        # foreach the automatic_step of step0 in config
        #   send the instruction to the serial
        for step in self.sysm.app_config.get("automatic_step","step"+str(current_step)):
            # If the instruction example are: delay0.0 or delay1 or delay0.55
            if(step.startswith("delay")):
                # Split the instruction to get the delay time
                delay_time = step.split("delay")[1]
                logger.debug(f"Delay for {delay_time} seconds")
                # Wait for the delay time
                time.sleep(float(delay_time))
            else:
                logger.debug(f"Prepare to send instuction {step} to serial")
                #If serial is busy, wait until it's idle
                while(self.seri.current_status["busy"]):
                    time.sleep(0.1)
                # Send the instruction to the serial
                self.seri.piInstruction(step)
                logger.debug(f"Instuction {step} sent to serial for execution")

        # Wait for the reset to finish
        logger.debug("Waiting for the instruction to finish")
        finish_count = 0
        while(self.seri.current_status["busy"] or finish_count <10):
            time.sleep(0.1)
            if(self.seri.current_status["busy"]):
                logger.debug("Instruction still running, Waiting for it to finish")
                finish_count = 0
            else:
                finish_count += 1

        logger.debug("Instruction finished")


    def runStep(self,step):
        # รีเซ็ตตำแหน่ง
        # คีบจากกล่อง
        # วางที่สายพาน
        # เลื่อนสายพาน
        # ตรวจรูปทรง
        # วางลงกล่อง

        if step == 0 : #Reset the arm to the initial position
            self.stepControl(0)
        elif step == 1: #Grab from the box
            for i, item in enumerate(self.status["items"]):
                if(item == 0):
                    logger.debug(f"Box number {i} is empty! Skippping this box")
                    continue
                else:
                    logger.debug(f"Box number {i} now has {item} items, Proceed to grab the item")
                    self.grabBox(i)
                    break
        
        elif step == 2: #Place the item on the conveyor
            self.stepControl(2)

        elif step == 3: #Move the conveyor
            self.stepControl(3)
            #Open camera
            self.tfma.startCamera()
            if(self.sysm.running["detect_flag"]):
                logger.debug("Shape detected, proceed to next step")
            else:
                logger.debug("Shape not detected")
            # Wait for sensor to detect the item
            logger.debug("Waiting for the sensor to detect the item")
            while(not self.seri.current_status["sensor"]):
                time.sleep(0.1)
            logger.debug("Item detected, proceed to next step")
            # Stop the camera
            #self.tfma.killThread()
            
            
        elif step == 4: #Detect the shape
            self.stepControl(4)
            #Detect the shape
            # if(self.sysm.running["detect_flag"]):
            #     logger.debug("Shape detected, proceed to next step")
            # else:
            #     logger.debug("Shape not detected")

        
        elif step == 5: #Place the item in the box
            self.stepControl(5)
            # If shape is detected, place the item in the box according to the shape
            logger.debug("Prepare to place the item in the box")


    def grabBox(self,box_number):
        # Check if the box is empty
        if(self.status["items"][box_number] == 0):
            logger.debug(f"Box number {box_number} is empty! Skippping this box")
            return False
        else:
            logger.debug(f"Box number {box_number} now has {self.status['items'][box_number]} items, Proceed to grab the item")
            for step in self.sysm.app_config.get("grab_step","grab"+str(box_number)):
                # If the instruction example are: delay0.0 or delay1 or delay0.55
                if(step.startswith("delay")):
                    # Split the instruction to get the delay time
                    delay_time = step.split("delay")[1]
                    logger.debug(f"Delay for {delay_time} seconds")
                    # Wait for the delay time
                    time.sleep(float(delay_time))
                else:
                    logger.debug(f"Prepare to send instuction {step} to serial")
                    #If serial is busy, wait until it's idle
                    while(self.seri.current_status["busy"]):
                        time.sleep(0.1)
                    # Send the instruction to the serial
                    self.seri.piInstruction(step)
                    logger.debug(f"Instuction {step} sent to serial for execution")
            # Wait for the grab to finish
            logger.debug(f"Waiting for the grab from box number {box_number} to finish")
            finish_count = 0
            while(self.seri.current_status["busy"] or finish_count <10):
                time.sleep(0.1)
                if(self.seri.current_status["busy"]):
                    logger.debug("Instruction still running, Waiting for it to finish")
                    finish_count = 0
                else:
                    finish_count += 1
                    
            logger.debug(f"Grab from box number {box_number} finished")
            # Update the box status
            self.status["items"][box_number] -= 1
            logger.debug(f"Box number {box_number} now has {self.status['items'][box_number]} items")
            return True
            
    def DropBox(self,box_number):
         for step in self.sysm.app_config.get("drop_step","drop"+str(box_number)):
                # If the instruction example are: delay0.0 or delay1 or delay0.55
                if(step.startswith("delay")):
                    # Split the instruction to get the delay time
                    delay_time = step.split("delay")[1]
                    logger.debug(f"Delay for {delay_time} seconds")
                    # Wait for the delay time
                    time.sleep(float(delay_time))
                else:
                    logger.debug(f"Prepare to send instuction {step} to serial")
                    #If serial is busy, wait until it's idle
                    while(self.seri.current_status["busy"]):
                        time.sleep(0.1)
                    # Send the instruction to the serial
                    self.seri.piInstruction(step)
                    logger.debug(f"Instuction {step} sent to serial for execution")
        


                



            






