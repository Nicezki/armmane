import os
from loguru import logger

from app import sysmane as smn
import threading
import time
import random


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
            "drop" : None,
            "sorting" : 0,
            "error": 0,
            "pickup_count" : [
                2,2,2,
            ],
            "items": [
                2,2,2,
            ],
            "alert":{
                "shuffle_currently": False,
                "grip_failed" : False,
                "not_find_object" : False,
                "not_recognize_object" : False,
                "not_recognize_object_limit" : False,
                "gripcheck_not_working": False,
                "grip_failed_limit" : False,
                "random_box_prediction" : False,
                "ignore_conv_sensor" : False, # Can be used to ignore the conveyor sensor (Set to True to ignore the sensor)
            },
            "flag":{
                "not_stop_camera" : False,
            }
        }

        # If OS is windows, set flag to ignore_conv_sensor to True
        if(os.name == "nt"):
            self.status["alert"]["ignore_conv_sensor"] = True
            logger.warning("OS is windows, set flag to ignore_conv_sensor to True")


    def getAlert(self):
        return self.status["alert"]

    def setSorting(self,sortNumber):
        self.status["sorting"] = sortNumber
        return True

    def getSorting(self):
        return self.status["sorting"]

    def getCurrentStatus(self):
        return self.status

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
    
    def setItem(self,box_number,item_number):
        self.status["items"][box_number-1] = item_number
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
            threading.Thread(target=self.autoMane).join()
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

            if(current_step <6):
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
                self.seri.piInstructionPreset(step)
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
            self.status["drop"] = None
            # Check if the grip sensor is working by trying to grab the item
            logger.debug("Checking grip sensor process started")
            logger.debug("Trying to grip...")
            self.stepControl(0.1)
            time.sleep(1)
            logger.debug("Checking if the grip sensor is working...")
            if(self.seri.getGripItemStatus() == True):
                logger.debug("Grip sensor is working")
                self.status["alert"]["gripcheck_not_working"] = False
            elif (self.seri.getGripItemStatus() == False):
                logger.error("Grip sensor is not working")
                self.status["alert"]["gripcheck_not_working"] = True
                self.status["step"] = 0
                return
            else:
                logger.error(f"Grip sensor return unknown value: {self.seri.getGripItemStatus()}")
                self.status["alert"]["gripcheck_not_working"] = True
                self.status["step"] = 0
                return
            logger.debug("Checking grip sensor process finished")


        elif step == 1: #Grab from the box
            self.status["alert"]["random_box_prediction"] = False
            for i, item in enumerate(self.status["pickup_count"]):
                if(item == 0):
                    logger.debug(f"Box number {i+1} is empty! Skippping this box")
                    continue
                else:
                    logger.debug(f"Box number {i+1} now has {item} items, Proceed to grab the item")
                    self.currentBox = i
                    # Grab result can be 0 = empty, 1 = success, 2 = failed, 3 = not started
                    grab_result = 3
                    grab_retry = 0
                    while grab_result == 3 or (grab_result == 2 and grab_retry < 5):
                        if grab_retry > 0:
                            logger.warning(f"Retrying grab from box number {i+1} - Attempt {grab_retry+1}")
                        grab_result = self.grabBox(i)
                        grab_retry += 1
                        if grab_result == 2:
                            logger.warning(f"Detected failed grab, retrying grab from box number {i+1}")
                            self.status["step"] = 1
                    if(grab_result == 2):
                        logger.error(f"Grab failed after {grab_retry} attempts, skip the box")
                        self.status["alert"]["grip_failed_limit"] = True
                    break
        
        elif step == 2: #Place the item on the conveyor
            self.stepControl(2)

        elif step == 3: #Move the conveyor
            self.stepControl(3)
            
        elif step == 4: #Detect the shape
            count = 0   
            self.status["drop"] = None
            self.stepControl(4)
            if self.status["alert"]["ignore_conv_sensor"]:
                logger.warning("Conveyor sensor is ignored, skip the conveyor sensor check")
                logger.warning("Trying with fixed delay instead (10 seconds)")
                time.sleep(10)
            else:
                # Wait for sensor to detect the item
                logger.debug("Waiting for the sensor to detect the item")
                while(not self.seri.current_status["sensor"]["value"]):
                    count = count+1
                    time.sleep(0.1)
                    logger.debug(count)
                    if count >= 120:
                        self.status["error"] = 404
                        logger.error("No object on conveyor")
                        self.stepControl(4.1)
                        self.status["step"] = 0
                        self.status["items"][self.currentBox] += 1
                        self.status["alert"]["not_find_object"] = True
                        break

            if self.status["step"] != 0:     
                self.status["error"] = 0
                self.stepControl(4.1)
                logger.debug("Item detected")
                self.status["alert"]["not_find_object"] = False
                #Open camera
                self.tfma.startCamera()
                time.sleep(1)
                #Detect the item
                self.tfma.startDetect()
                time.sleep(3)
                # if self.sysm.running["current_classes"] != None:
                #     result = self.sysm.running["current_classes"].split("_")
                #     logger.debug(result)
                    #Chose which box to be drop
                while self.status["drop"] == None:
                    if self.sysm.running["current_classes"] != None and self.sysm.running["current_classes"] != "":
                        result = self.sysm.running["current_classes"].split("_")
                        logger.debug(result)
                        if (self.status["sorting"] == 0) :
                            logger.debug("IN SHAPE")
                            if result[1] == "Square":
                                self.status["drop"] = 0
                            elif result[1] == "Triangle":
                                self.status["drop"] = 1
                            elif result[1] == "Cylinder":
                                self.status["drop"] = 2

                        elif (self.status["sorting"] == 1) :
                            logger.debug("IN COLOR")
                            if result[0] == "Red":
                                self.status["drop"] = 0
                            elif result[0] == "White":
                                self.status["drop"] = 1
                            elif result[0] == "Blue":
                                self.status["drop"] = 2
                        else : 
                            logger.debug("IN RANDOM")
                            self.status["alert"]["random_box_prediction"] = True
                            self.status["drop"] = random.randrange(3)
                        logger.debug(f"drop box : {self.status['drop']} ")
                        break

                    
                    if(self.status["sorting"] == 0):
                        logger.debug("Can not detect any shape")
                    
                    elif(self.status["sorting"] == 1):
                        logger.debug("Can not detect any color")

                    else:
                        logger.debug("Can not detect any object")

                    self.status["alert"]["not_recognize_object"] = True

                    logger.debug("Instruction Failed, trying to reverse the conveyor")
  
                    while True:
                        count = count+1
                        self.status["error"] +=1
                        logger.debug("Trying to reverse the conveyor (Attempt "+str(count)+")" )
                        self.stepControl(4.3) #Reverse the conveyor
                        time.sleep(1)
                        self.stepControl(4) #Move the conveyor normally
                        if count > 5 :
                            self.status["alert"]["not_recognize_object_limit"] = True

                        if self.sysm.running["current_classes"] != None:
                            self.status["alert"]["not_recognize_object"] = False
                            self.status["alert"]["not_recognize_object_limit"] = False

                        if count >5 or self.sysm.running["current_classes"] != None:
                            break

    


                if(self.status["sorting"] == 0):
                    logger.debug("Shape detected, Stop detection and camera for better performance :)")

                elif(self.status["sorting"] == 1):
                    logger.debug("Color detected, Stop detection and camera for better performance :)")

                else:
                    logger.debug("Object detected, Stop detection and camera for better performance :)")

                self.status["alert"]["not_recognize_object"] = False
                # Stop the camera
                self.tfma.stopDetect()
                time.sleep(1)
                self.tfma.stopCamera()
                logger.debug("Proceed to next step")
                self.stepControl(4.4) #Move the conveyor > Close gate > Stop the conveyor > Open gate
                self.stepControl(4.2) # Prepre grip


        elif step == 5: #Place the item in the box
            self.stepControl(5)
            # If shape is detected, place the item in the box according to the shape
            logger.debug("Prepare to drop the item in the box")
            if(self.status["drop"] == None):
                self.status["alert"]["random_box_prediction"] = True
                logger.error("Drop box is not set, This indicate that the shape is not detected")
                logger.warning("Instruction Failed, Trying to fill the random box that not have 2 items")
                # If the shape is not detected, try to fill the box that not have 2 items
                for i, item in enumerate(self.status["items"]):
                    if(item < 2):
                        self.dropBox(i)
                        logger.warning(f"Trying to fill the box number {i+1} because it has {item} items")
                        break
                self.status["step"] = 1
                self.status["alert"]["random_box_prediction"] = False
                return
            self.dropBox(self.status["drop"])
        
        elif step == 6 and self.status["pickup_count"] == [0,0,0]:
            logger.debug("All object are in the correct box, shuffling the object")
            self.status["alert"]["shuffle_currently"] = True
            self.shuffleObject()
            self.status["alert"]["shuffle_currently"] = False
            logger.debug("Finished shuffling the object")
            self.status["pickup_count"] = self.status["items"]
            logger.debug(self.status["pickup_count"])

    def grabBox(self,box_number):
        # Check if the box is empty
        if(self.status["items"][box_number] == 0):
            logger.debug(f"Box number {box_number+1} is empty! Skippping this box")
            return 0
        else:
            logger.debug(f"Box number {box_number+1} now has {self.status['items'][box_number]} items, Proceed to grab the item")
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
                    self.seri.piInstructionPreset(step)
                    logger.debug(f"Instuction {step} sent to serial for execution")
            # Wait for the grab to finish
            logger.debug(f"Waiting for the grab from box number {box_number+1} to finish")
            finish_count = 0
            while(self.seri.current_status["busy"] or finish_count <10):
                time.sleep(0.1)
                if(self.seri.current_status["busy"]):
                    logger.debug("Instruction still running, Waiting for it to finish")
                    finish_count = 0
                else:
                    finish_count += 1

            #Check is grab sensor is working
            if(self.status["alert"]["gripcheck_not_working"]):
                logger.warning("Grip sensor is not working, skip the item grip check")
            else:
                # Chrck if the grab is success
                if(self.seri.getGripItemStatus() == False):
                    logger.success(f"[Grip Check] Grab from box number {box_number+1} success")
                    self.status["alert"]["grip_failed"] = False
                elif(self.seri.getGripItemStatus() == True):
                    logger.error(f"[Grip Check] Grab from box number {box_number+1} failed")
                    self.status["alert"]["grip_failed"] = True
                    # Retry the grab process
                    logger.warning(f"Detected failed grab, retrying grab from box number {box_number+1}")
                    return 2
                else:
                    logger.error(f"[Grip Check] Grip sensor return unknown value: {self.seri.getGripItemStatus()}")
                    logger.warning("Grip sensor is not working, skip the item grip check")
    
                    
            logger.debug(f"Grab from box number {box_number+1} finished")
            # Update the box status
            self.status["pickup_count"][box_number] -= 1
            self.status["items"][box_number] -= 1
            logger.debug(f"Box number {box_number+1} now has {self.status['items'][box_number]} items")
            return 1
            


    def dropBox(self,box_number):
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
                # Lookup the instruction preset
                # piInstructionPreset
                self.seri.piInstructionPreset(step)
                
                logger.debug(f"Instuction {step} sent to serial for execution")
            
        # Wait for the drop to finish
        logger.debug(f"Waiting for the drop to box number {box_number} to finish")
        finish_count = 0
        while(self.seri.current_status["busy"] or finish_count <10):
            time.sleep(0.1)
            if(self.seri.current_status["busy"]):
                logger.debug("Instruction still running, Waiting for it to finish")
                finish_count = 0
            else:
                finish_count += 1
                
        logger.debug(f"Drop to box number {box_number} finished")
        self.status["items"][box_number] += 1
        logger.debug(f"Box number {box_number+1} now has {self.status['items'][box_number]} items")
        return True

    def shuffleObject(self):
        self.status["alert"]["shuffle_currently"] = True
        i = 0
        while i <= 5 :
            i += 1
            random_pickup = random.randrange(len(self.status["items"]))
            if self.status["items"][random_pickup] == 0 :
              i -= 1
              continue
            else :
               random_dropbox = random.randrange(len(self.status["items"]))
               logger.debug(f"Pickup from box {random_pickup}")
               self.grabBox(random_pickup)
               logger.debug(f"drop to box {random_dropbox}")
               self.dropBox(random_dropbox)
        self.status["alert"]["shuffle_currently"] = False
        #return random_pickup, random_dropbox
    
