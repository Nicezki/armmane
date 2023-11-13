import serial
import serial.tools.list_ports
import threading
from loguru import logger
import platform
import RPi.GPIO as GPIO
import time
import psutil


class SeriMane:
    def __init__(self, sysmane):
        self.sysmane = sysmane
        self.current_status = {
            "port" : None,
            "ready" : False,
            "busy" : False,
            'servo' : [80,75,80,75,0,45,0],
            'conv' : {
                'mode' : [0,0],
                'speed' : [0,0]
            },
            'sensor' : {
                'init' : None,
                'available' : False,
                'value' : False
            },
            "statuscode" : "none",
            "instruction" : None,
            "status" : "Initualizing",
            "message" : "Initualizing Arduino connection",
            "queue" : [],
            "gripdetect" : False,
            "emergency" : False,
            "system": {
                "os": platform.system(),
                "version": platform.version(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "network": psutil.net_io_counters()
            },
            "alert":{
                "arduino_not_found": True,
                "windows_detected": False,
                "sensor_not_working": True,
                "emergency_mode_activated": False,
                "sending_message_failed": False,
                "high_cpu_usage": False,
                "high_memory_usage": False,
                "high_disk_usage": False,
            }
        }

        self.sensor = None
        self.arduino_port = None
        self.arduino = None
        self.current_status["emergency"] = False
        self.extended_log = False


        #FOR DEBUG WITHOUT ARDUINO ON WINDOWS ONLY!
        self.preview_mode_non_arduino = False


        #If Windows detected, set preview mode to True
        if platform.system() == "Windows":
            self.preview_mode_non_arduino = True
            self.log("Windows detected, preview mode with no arduino is on", "Windows", "warning")
        



        while not self.arduino_port and self.arduino is None:
            self.initArduinoPort()
            time.sleep(1)


        self.receive_thread = threading.Thread(target=self.receiveMessages)
        # self.receive_thread = threading.Thread(counter=self.timeCount)
        self.receive_thread.daemon = True 
        self.receive_thread.start()

        if platform.system() != "Linux":
            self.log("Windows detected, skipping GPIO setup", "Windows", "warning")
            self.current_status["alert"]["windows_detected"] = True

        else: 
            # Initialize GPIO for the obstacle sensor
            self.sensor_pin = 17  # Use the GPIO number, not the physical pin number
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.sensor_pin, GPIO.IN)
            GPIO.setup(18, GPIO.IN)
            self.log("GPIO setup done", "GPIO", "success")

        self.prepare()
        
        


    # When destroy is called
    def __del__(self):
        self.closeConnection()
        if platform.system() != "Linux":
            GPIO.cleanup()
            if self.obstacle_thread:
                self.obstacle_thread.join()
            if self.sensor_thread:
                self.sensor_thread.join()

            self.obstacle_thread = None
            self.sensor_thread = None
        
        if self.receive_thread:
            self.receive_thread.join()


        # Clear the thread
        self.receive_thread = None

    def updateSystemStatus(self):
        while True:
            self.current_status["system"]["cpu_usage"] = psutil.cpu_percent()
            self.current_status["system"]["memory_usage"] = psutil.virtual_memory().percent
            self.current_status["system"]["disk_usage"] = psutil.disk_usage('/').percent
            self.current_status["system"]["network"] = psutil.net_io_counters()
            # Check if the CPU usage is high
            if self.current_status["system"]["cpu_usage"] > 80:
                self.log(f"CPU usage is high ({self.current_status['system']['cpu_usage']}%)", "CPU", "warning")
                self.current_status["alert"]["high_cpu_usage"] = True
            else:
                self.current_status["alert"]["high_cpu_usage"] = False
            # Check if the memory usage is high
            if self.current_status["system"]["memory_usage"] > 80:
                self.log(f"Memory usage is high ({self.current_status['system']['memory_usage']}%)", "Memory", "warning")
                self.current_status["alert"]["high_memory_usage"] = True
            else:
                self.current_status["alert"]["high_memory_usage"] = False
            # Check if the disk usage is high
            if self.current_status["system"]["disk_usage"] > 80:
                self.log(f"Disk usage is high ({self.current_status['system']['disk_usage']}%)", "Disk", "warning")
                self.current_status["alert"]["high_disk_usage"] = True
            else:
                self.current_status["alert"]["high_disk_usage"] = False
            time.sleep(3)

    def updateGripStatus(self):
        while True:
            self.current_status["gripdetect"] = self.getGripItemStatus()
            # logger.info(f"Grip status: {self.current_status['gripdetect']}")
            time.sleep(0.5)

    def getGripStatus(self):
        return self.current_status["gripdetect"]
    

    def getAlert(self):
        return self.current_status["alert"]
    

    def initArduinoPort(self):
        self.arduino_port = self.findArduinoPort()
        if self.arduino_port:
            self.log("Arduino found on port: " + str(self.arduino_port), "Found", "success")
            self.log("Connecting to Arduino with baudrate: " + str(self.sysmane.app_config.get("serial_buadrate")), "Connecting", "debug")
            self.arduino = serial.Serial(self.arduino_port, self.sysmane.app_config.get("serial_buadrate"), timeout=1)   
            self.log("Connected to Arduino", "Connected", "success")
            self.current_status["alert"]["arduino_not_found"] = False
        else:
            if(self.preview_mode_non_arduino):
                self.log("Arduino not found, But preview mode is on, so I will continue", "Not found", "warning")
                self.current_status["alert"]["arduino_not_found"] = False
                self.arduino = True
            else:
                self.log("Arduino not found Trying again in 1 second", "Not found", "warning")
                # Retry to find Arduino
                self.arduino = None
                self.current_status["alert"]["arduino_not_found"] = True


    def setEmergency(self, emergency):
        self.current_status["emergency"] = emergency
        if emergency:
            self.log("Emergency mode activated", "Emergency", "warning")
            self.current_status["alert"]["emergency_mode_activated"] = True
        else:
            self.log("Emergency mode deactivated", "Emergency", "success")
            self.current_status["alert"]["emergency_mode_activated"] = False




    def prepare(self):
        # Add thread for updating system status
        self.system_thread = threading.Thread(target=self.updateSystemStatus)
        self.system_thread.daemon = True
        self.system_thread.start()

        # Add thread for updating grip status
        self.grip_thread = threading.Thread(target=self.updateGripStatus)
        self.grip_thread.daemon = True
        self.grip_thread.start()


        # self.compat_checkCurrentState()
        # self.compat_checkBusy()
        # Start a thread for obstacle detection
        if platform.system() != "Linux":
            self.log("Windows detected, skipping obstacle detection", "Windows", "warning")
            # Set default value for sensor
            self.current_status["sensor"]["init"] = True
            self.current_status["sensor"]["available"] = True
            self.current_status["sensor"]["value"] = False
        else:
            self.obstacle_thread = threading.Thread(target=self.detectObstacle)
            self.obstacle_thread.daemon = True
            self.obstacle_thread.start()
            self.sensor_thread = threading.Thread(target=self.timeCount)
            self.sensor_thread.start()
            

    def timeCount(self):
        time.sleep(5)
        if self.current_status["sensor"]["init"] != True:
            time.sleep(5)
            self.log("No sensor found, please find one for me pretty please >,< ")
            self.current_status["alert"]["sensor_not_working"] = True
            self.current_status["sensor"]["init"] == True
        # else:
            # self.sensor_thread.join()``
        
    def detectObstacle(self):
        while True:   
            # Read the digital value from the obstacle sensor
            if self.current_status["sensor"]["init"] == None or self.current_status["sensor"]["init"] == True :
                counterout = 0
                sensor_value = GPIO.input(self.sensor_pin)
                if sensor_value == GPIO.HIGH:
                    # self.log("No obstacle detected")
                    self.current_status["sensor"]["value"] = False
                    counterout = counterout+1
                    if counterout == 10:
                        counterout = 0
                        self.current_status["sensor"]["init"] = False
                        self.sensor_thread = threading.Thread(target=self.timeCount)
                        self.sensor_thread.start()
                else:
                    # self.log("Obstacle detected")
                    self.current_status["sensor"]["init"] = True 
                    self.current_status["sensor"]["available"] = True
                    self.current_status["sensor"]["value"] = True
                    self.current_status["alert"]["sensor_not_working"] = False
                time.sleep(0.5)  # Adjust the sleep time as needed
            else:
                logger.error("No sensor")
                time.sleep(0.5)
                continue

    def log(self, message, status=None, level="info"):
        # Store the status
        if status:
            self.current_status["status"] = status
        # Store the message
        self.current_status["message"] = message
        # Log the message
        if level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        elif level == "success":
            logger.success(message)
        elif level == "debug":
            logger.debug(message)
        elif level == "exception":
            logger.exception(message)
        elif level == "critical":
            logger.critical(message)
        elif level == "trace":
            logger.trace(message)
        else:
            logger.debug(message)
        
    def findArduinoPort(self):
        arduino_vid = '2341'  # Vendor ID of Arduino
        arduino_pid = '0043'  # Product ID of Arduino

        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            self.log(f"Trying to connect to port: {port}", "Connecting", "debug")
            if port.vid == int(arduino_vid, 16) and port.pid == int(arduino_pid, 16):
                self.log(f"Found Arduino on port: {port}", "Found", "success")
                self.current_status["port"] = port.device
                return port.device

        return None
    def getCurrentStatus(self):
        return self.current_status


    def sendMessageToArduino(self, message):
        # # Check if ardunio is connected and ready
        # if not self.isArduinoReady:
        #     logger.error("Arduino not ready, cannot send message.")
        #     return None

        if self.preview_mode_non_arduino:
            self.log(f"Preview mode is on, message will not be sent to Arduino: {message}", "Preview", "warning")
            return "ok", self.current_status

        if self.current_status["emergency"]:
            self.log("Emergency mode is activated, cannot send message.", "Emergency", "error")
            # Trying to disconnect from Arduino and reconnect again
            self.arduino = None
            while self.current_status["emergency"]:
                time.sleep(1)
                self.log("[!] Emergency mode is activated [!]", "Emergency", "error")
                self.log("Please press the unlock button to continue", "Emergency", "error")
                self.log("or send API POST request to \"/command/unlock\" to unlock", "Emergency", "error")
                self.log("Waiting for unlock button to be pressed...", "Emergency", "error")
                continue
            # Count the retry
            retry_count = 0
            while not self.arduino and retry_count < 100:
                self.initArduinoPort()
                retry_count += 1
                self.log("[Emergency Stop] Trying to reconnect to Arduino... (Trying " + str(retry_count) + " of 100)", "Reconnecting", "warning")
                time.sleep(1)

        if self.arduino:
            # if self.current_status["busy"]:
            #     self.log("Arduino is busy, cannot send message.", "Busy", "error")
            #     return "busy", self.current_status
            if self.arduino:
                if self.extended_log:
                    self.log(f"Sending message to Arduino: {message}", "Sending")
                # self.log(f"<<-- Message sent to Arduino: {message}", "Sent", "debug")
                try:
                    self.arduino.write((message + '\n').encode())  # Send the message to Arduino
                    if self.extended_log:
                        self.log(f"Message sent to Arduino: {message}", "Sent", "success")
                        self.current_status["alert"]["sending_message_failed"] = False
                    return "ok", self.current_status
                except Exception as e:
                    self.log(f"Error while sending message to Arduino: {e}", "Error", "error")
                    self.current_status["alert"]["sending_message_failed"] = True
                    # Try to reconnect to Arduino
                    self.arduino = None
                    # Count the retry
                    retry_count = 0
                    while not self.arduino and retry_count < 100:
                        self.initArduinoPort()
                        retry_count += 1
                        self.log("Trying to reconnect to Arduino... (Trying " + str(retry_count) + " of 100)", "Reconnecting", "warning")
                        time.sleep(1)
                    return "error", self.current_status
                
            else:
                self.log("Arduino not found, cannot send message.", "Error", "error")
                self.current_status["alert"]["sending_message_failed"] = True
                return "error", self.current_status
        else:
            self.log("Arduino not found, cannot send message.", "Error", "error")
            self.current_status["alert"]["sending_message_failed"] = True
            return "error", self.current_status



    def receiveMessages(self):
        while True:
            if self.preview_mode_non_arduino:
                continue
            if self.arduino:
                line = str(self.arduino.readline().decode().strip())
                # If the line is empty, skip it
                if not line:
                    continue
                if self.extended_log:
                    self.log(f"-->> Received message from Arduino: {line}", "Received", "debug")
                # If the line is "Ready!", set isArduinoReady to True
                if line == "Ready!":
                    self.current_status["ready"] = True
                    self.log("Arduino is ready.", "Ready", "success")
                    # self.checkCurrentState()
                    # self.checkBusy()
                    continue
                # INST{number} is the instruction number start from 0 and increase by 1 every time the instruction is sent
                if line.startswith("INST"):
                    self.current_status["instruction"] = line
                    continue
    

    # def compat_receiveMessages(self):
    #     while True:
    #         if self.arduino:
    #             line = str(self.arduino.readline().decode().strip())
    #             # If the line is empty, skip it
    #             if not line:
    #                 continue
    #             #self.log(f"-->> Received message from Arduino: {line}", "Received", "debug")
    #             # If the line is "Ready!", set isArduinoReady to True
    #             if line == "Ready!":
    #                 self.current_status["ready"] = True
    #                 self.log("Arduino is ready.", "Ready", "success")
    #                 self.compat_checkCurrentState()
    #                 self.compat_checkBusy()
    #                 continue
    #             if line == "PB":
    #                 self.current_status["busy"] = True
    #                 self.log("Arduino is busy.", "Busy", "warning")
    #                 continue
    #             if line == "POK":
    #                 self.current_status["ready"] = True
    #                 self.current_status["busy"] = False
    #                 self.log("Arduino is not busy.", "Ready", "success")
    #                 continue
    #             if line.startswith("PS") or line.startswith("PF"):
    #                 logger.info(f"Status received: {line}")
    #                 self.current_status["instruction"] = self.compat_extractInstruction(line)
    #                 self.current_status["statuscode"] = line
    #             else: self.log(f"{line}", "Arduino", "debug")
    #         else:
    #             self.log("Arduino not found, cannot receive message.", "Error", "trace")
    #             return None
    






    # def compat_checkCurrentState(self):
    #     self.sendMessageToArduino("PC")
        
    # def compat_checkBusy(self):
    #     self.sendMessageToArduino("PB")

    # def compat_piInstruction(self, action):
    #     instruction = self.sysmane.app_config.get("instructions")

    #     #Check if the action is in the instruction list if not return error
    #     if action not in instruction:
    #         self.log(f"Action {action} not found in instruction list", "Error", "error")
    #         return None
        
    #     # Convert to old format
    #     step = instruction[action]["step"]
    #     old_format = ">".join(step) + ">END"
        
    #     # Send the instruction to Arduino with PX(Instruction)
    #     self.sendMessageToArduino("PX" + old_format)
    #     self.log(f"Instruction sent: {old_format}")


    def piInstructionPreset(self, action):
        instruction = self.sysmane.app_config.get("instructions")

        #Check if the action is in the instruction list if not return error
        if action not in instruction:
            self.log(f"Action {action} not found in instruction list", "Error", "error")
            return None
        
        # Convert to old format
        # step = instruction[action]["step"]
        # old_format = ">".join(step) + ">END"
        
        # # Send the instruction to Arduino with PX(Instruction)
        # self.sendMessageToArduino("PX" + old_format)
        # self.log(f"Instruction sent: {old_format}")    

        # Convert to new format
        step = instruction[action]["step"]
        # Put in to the function "translatePiInstruction"
        # Loop through the step
        for i in step:
            #logger.info(f"Converting instruction: {i}")
            self.translatePiInstruction(i)
            time.sleep(0.5)
        self.log(f"Instruction sent: {step}")




    def translatePiInstruction(self, action):
        if(action.startswith("S")):
        #     S0D180 -> set servo 0 to 180 degree
            servo = int(action[1:3])
            degree = int(action[4:7])
            #logger.info(f"[Converted] Setting servo {servo} to {degree} degree")
            self.setSmoothServo(servo, degree)
            return None
        elif(action.startswith("C")):
        #     C0M1S255 -> set conveyor 0 to mode 1 at speed 255
            conveyor = int(action[1:2])
            mode = int(action[3:4])
            speed = int(action[5:8])
            #logger.info(f"[Converted] Setting conveyor {conveyor} to mode {mode} at speed {speed}")
            self.setConveyor(conveyor, mode, speed)
            return None
        else:
            self.log(f"Action {action} not found in instruction list", "Error", "error")
            return None


    def getGripItemStatus(self):
        # Get digitalread of pin 18
        # If HIGH, return True
        # If LOW, return False
        if GPIO.input(18) == GPIO.HIGH:
            return True
        else:
            return False
        
        



    def setSmoothServo(self, servo, degree):
        # Check if the servo is in range
        if servo < 0 or servo > int(self.sysmane.app_config.get("servo_count")):
            self.log(f"Servo {servo} not in range (0, {self.sysmane.app_config.get('servo_count')})", "Error", "error")
            return None
        if degree < int(self.sysmane.app_config.get("servo_min_degree")) or degree > int(self.sysmane.app_config.get("servo_max_degree")):
            self.log(f"Degree {degree} not in range ({self.sysmane.app_config.get('servo_min_degree')}, {self.sysmane.app_config.get('servo_max_degree')})", "Error", "error")
            return None

        # Wait for the arduino to not busy
        while self.current_status["busy"]:
            logger.warning("[Jotto matte!!] Arduino is busy, waiting for 0.2 second...")
            time.sleep(0.2)

        # Smoothly move the servo to the desired degree
        # Desired degree is the degree that we want to move to
        desired_degree = degree
        # Current degree is the current degree of the servo
        current_degree = self.current_status["servo"][servo]
        # Step is the number of steps that we want to move
        step = int(self.sysmane.app_config.get("servo_step"))
        # Delay is the delay between each step
        delay = float(self.sysmane.app_config.get("servo_delay"))
        # Calculate the difference between the desired degree and current degree
        degree_diff = desired_degree - current_degree
        #logger.info(f"Servo {servo} at {current_degree} degree, need to move {degree_diff} degree to {desired_degree} degree")
        
        # If the difference is 0, do nothing
        if degree_diff == 0:
            #logger.info(f"Servo {servo} is already at {desired_degree} degree")
            self.setServo(servo, desired_degree)
            return None
        
        # If the difference is positive, move clockwise
        if degree_diff > 0:
            #logger.info(f"Servo {servo} is moving clockwise")
            # Loop from current degree to desired degree
            for i in range(current_degree, desired_degree + 1, step):
                # Set the servo to the current degree
                self.setServo(servo, i)
                # Wait for delay
                time.sleep(delay)

        # If the difference is negative, move counter-clockwise
        if degree_diff < 0:
            #logger.info(f"Servo {servo} is moving counter-clockwise")
            # Loop from current degree to desired degree
            for i in range(current_degree, desired_degree - 1, -step):
                # Set the servo to the current degree
                self.setServo(servo, i)
                # Wait for delay
                time.sleep(delay)

        
        # Set the servo to the desired degree
        self.setServo(servo, desired_degree)
        # Set flag to not busy
        self.current_status["busy"] = False

    # def queueInstruction(self, instruction):
    #     self.current_status["queue"].append(instruction)
    #     self.log(f"Instruction queued: {instruction}", "Queued", "info")

    # def executeQueue(self):
    #     if len(self.current_status["queue"]) > 0:
    #         instruction = self.current_status["queue"].pop(0)
    #         self.log(f"Executing instruction: {instruction}", "Executing", "info")
    #         self.piInstructionPreset(instruction)
    #         return True



    def setServo(self, servo, degree):
        # New output serial format is {servo0}{servo1}{servo2}{servo3}{servo4}{servo5}{conv0mode}{conv0speed}{conv1mode}{conv1speed}
        # Example: 18018018018018018012551255        
        # Check if the servo is in range
        if servo < 0 or servo > int(self.sysmane.app_config.get("servo_count")):
            self.log(f"Servo {servo} not in range (0, {self.sysmane.app_config.get('servo_count')})", "Error", "error")
            return None
        if degree < int(self.sysmane.app_config.get("servo_min_degree")) or degree > int(self.sysmane.app_config.get("servo_max_degree")):
            self.log(f"Degree {degree} not in range ({self.sysmane.app_config.get('servo_min_degree')}, {self.sysmane.app_config.get('servo_max_degree')})", "Error", "error")
            return None

        # Prepare the output string based on the current status and the desired servo and degree
        # Example: setServo(0, 180) will set servo 0 to 180 degree
        # If last status is 17918018018018018012551255
        # so the output string will be 18018018018018018012551255 (change the first 3 digits)

        # Convert the degree to 3 digits
        degree = str(degree).zfill(3)

        servo0 = self.current_status["servo"][0]
        servo1 = self.current_status["servo"][1]
        servo2 = self.current_status["servo"][2]
        servo3 = self.current_status["servo"][3]
        servo4 = self.current_status["servo"][4]
        servo5 = self.current_status["servo"][5]
        servo6 = self.current_status["servo"][6]
        conv0mode = self.current_status["conv"]["mode"][0]
        conv0speed = self.current_status["conv"]["speed"][0]
        conv1mode = self.current_status["conv"]["mode"][1]
        conv1speed = self.current_status["conv"]["speed"][1]


        if servo == 0:
            servo0 = degree
        elif servo == 1:
            servo1 = degree
        elif servo == 2:
            servo2 = degree
        elif servo == 3:
            servo3 = degree
        elif servo == 4:
            servo4 = degree
        elif servo == 5:
            servo5 = degree
        elif servo == 6:
            servo6 = degree
        else:
            self.log(f"Servo {servo} not in range (0, {self.sysmane.app_config.get('servo_count')})", "Error", "error")
            return None
        
        output = f"{str(servo0).zfill(3)}{str(servo1).zfill(3)}{str(servo2).zfill(3)}{str(servo3).zfill(3)}{str(servo4).zfill(3)}{str(servo5).zfill(3)}{str(servo6).zfill(3)}{conv0mode}{str(conv0speed).zfill(3)}{conv1mode}{str(conv1speed).zfill(3)}"
        
        # Set current_status["servo"] to the new degree
        self.current_status["servo"][servo] = int(degree)

        # Send the instruction to Arduino
        self.sendMessageToArduino(output)


    def setConveyor(self, conveyor, mode=None, speed=None):
        # New output serial format is {servo0}{servo1}{servo2}{servo3}{servo4}{servo5}{conv0mode}{conv0speed}{conv1mode}{conv1speed}
        # Example: 18018018018018018012551255        
        # Check if the conveyor is in range
        if conveyor < 0 or conveyor > int(self.sysmane.app_config.get("conveyor_count")):
            self.log(f"Conveyor {conveyor} not in range (0, {self.sysmane.app_config.get('conveyor_count')})", "Error", "error")
            return None
        if mode is None and speed is None:
            self.log(f"Conveyor {conveyor} is not set", "Error", "error")
            return None
        if mode is None:
            mode = self.current_status["conv"]["mode"][conveyor]
        if speed is None:
            speed = self.current_status["conv"]["speed"][conveyor]

        servo0 = self.current_status["servo"][0]
        servo1 = self.current_status["servo"][1]
        servo2 = self.current_status["servo"][2]
        servo3 = self.current_status["servo"][3]
        servo4 = self.current_status["servo"][4]
        servo5 = self.current_status["servo"][5]
        servo6 = self.current_status["servo"][6]

        conv0mode = self.current_status["conv"]["mode"][0]
        conv0speed = self.current_status["conv"]["speed"][0]
        conv1mode = self.current_status["conv"]["mode"][1]
        conv1speed = self.current_status["conv"]["speed"][1]

        # Prepare the output string based on the current status and the desired servo and degree
        if conveyor == 0:
            conv0mode = mode
            conv0speed = speed
        elif conveyor == 1:
            conv1mode = mode
            conv1speed = speed
        else:
            self.log(f"Conveyor {conveyor} not in range (0, {self.sysmane.app_config.get('conveyor_count')})", "Error", "error")
            return None
        

        output = f"{str(servo0).zfill(3)}{str(servo1).zfill(3)}{str(servo2).zfill(3)}{str(servo3).zfill(3)}{str(servo4).zfill(3)}{str(servo5).zfill(3)}{str(servo6).zfill(3)}{conv0mode}{str(conv0speed).zfill(3)}{conv1mode}{str(conv1speed).zfill(3)}"

        # Set current_status["conv"] to the new mode and speed
        self.current_status["conv"]["mode"][conveyor] = mode
        self.current_status["conv"]["speed"][conveyor] = speed

        # Send the instruction to Arduino
        self.sendMessageToArduino(output)


    # def compat_setServo(self, servo, degree):
    #     # Check if the servo is in range
    #     if servo < 0 or servo > int(self.sysmane.app_config.get("servo_count")):
    #         self.log(f"Servo {servo} not in range (0, {self.sysmane.app_config.get('servo_count')})", "Error", "error")
    #         return None

    #     # Check if the degree is in range (min, max)
    #     if degree < int(self.sysmane.app_config.get("servo_min_degree")) or degree > int(self.sysmane.app_config.get("servo_max_degree")):
    #         self.log(f"Degree {degree} not in range ({self.sysmane.app_config.get('servo_min_degree')}, {self.sysmane.app_config.get('servo_max_degree')})", "Error", "error")
    #         return None

    #     # convert the degree to 3 digits
    #     degree = str(degree).zfill(3)

    #     # convert the servo to 2 digits
    #     servo = str(servo).zfill(2)

    #     # Send the instruction to Arduino with PIS(Servo)D(Degree)
    #     self.sendMessageToArduino(f"PXS{servo}D{degree}>END")



        

    # def compat_setConveyor(self, conveyor, mode=None, speed=None):
    #     if mode is None and speed is None:
    #         self.log(f"Conveyor {conveyor} is not set", "Error", "error")
    #         return None
    #     if mode is None:
    #         mode = self.current_status["conv"]["mode"][conveyor]
    #     if speed is None:
    #         speed = self.current_status["conv"]["speed"][conveyor]
        
    #     # Check if the conveyor is in range
    #     if conveyor < 0 or conveyor > int(self.sysmane.app_config.get("conveyor_count")):
    #         self.log(f"Conveyor {conveyor} not in range (0, {self.sysmane.app_config.get('conveyor_count')})", "Error", "error")
    #         return None
        
    #     #Format CXY where X is conveyor number and Y is mode
    #     # Check if the mode is in range (0, 1, 2)
    #     if mode < 0 or mode > 2:
    #         self.log(f"Mode {mode} not in range (0, 1, 2)", "Error", "error")
    #         return None
        
    #     if speed <0: speed = 0
    #     if speed > 255: speed = 255
        
    #     # convert the mode to 1 digits
    #     mode = str(mode).zfill(1)

    #     # convert the conveyor to 1 digits
    #     conveyor = str(conveyor).zfill(1)

    #     # Send the instruction to Arduino with PIC(Conveyor)(Mode)
    #     self.sendMessageToArduino(f"PXC{conveyor}M{mode}S{str(speed).zfill(3)}>END")


    def closeConnection(self):
        if self.arduino:
            self.arduino.close()
            self.log("Serial connection to Arduino closed.", "Closed", "info")

    # def compat_extractInstruction(self, input):
    #     Mode = 0
    #     ServoDegree = [0, 0, 0, 0, 0, 0]
    #     ConvState = [0, 0]
    #     ConvSpeed = [0, 0]
    #     isCompleteReading = False
    #     try:
    #         # Split input by 'S' to separate servo data
    #         servo_data_parts = input.split('S')[1:7]  # Skip the first element

    #         for i, data_part in enumerate(servo_data_parts):
    #             servo_number = i
    #             # Locate the 'D' separator within each servo data part
    #             d_index = data_part.find('D')
    #             if d_index != -1:  # Check if 'D' separator was found
    #                 degree_str = data_part[d_index + 1:d_index + 4]  # Extract 3 characters for the degree part
    #                 if degree_str:
    #                     degree = int(degree_str)
    #                     ServoDegree[servo_number] = degree
    #                 else:
    #                     # Handle the case where degree_str is empty or not a valid integer
    #                     ServoDegree[servo_number] = 0  # or some default value, depending on your requirements

    #         # Split input by 'C' to separate conveyor data
    #         #C0M{mode}S{speed}C1M{mode}S{speed}
    #         # Mode is 1 digit start from 0 to 2
    #         # Speed is 3 digit start from 000 to 255
    #         # input.split('C') return ['PS00D000S01D000S02D000S03D000S04D000S05D000', '0M0S000', '1M0S000']
    #         # print (input.split('C'))
    #         # print (f"CVState0: {input.split('C')[1][2:3]} | CVSpeed0: {input.split('C')[1][4:7]} | CVState1: {input.split('C')[2][2:3]} | CVSpeed1: {input.split('C')[2][4:7]}")
    #         ConvState[0] = int(input.split('C')[1][2:3])
    #         ConvSpeed[0] = int(input.split('C')[1][4:7])
    #         ConvState[1] = int(input.split('C')[2][2:3])
    #         ConvSpeed[1] = int(input.split('C')[2][4:7])
    #         # self.log(f"C0 is {ConvState[0]} at speed {ConvSpeed[0]}| C1 is {ConvState[1]} at speed {ConvSpeed[1]}", "Instruction", "debug")

    #         if input.startswith("PS"):
    #             Mode = 1
    #         elif input.startswith("PF"):
    #             Mode = 2

    #         instruction = f"[Instruction] {'Smooth' if Mode == 1 else 'Force'}"
    #         servo_info = ', '.join([f"S{i} at {degree} degree" for i, degree in enumerate(ServoDegree)])
    #         conveyor_info = ', '.join([f"Conveyor {i} is {'forward' if mode == 1 else 'stop' if mode == 0 else 'backward'}" for i, mode in enumerate(ConvState)])
    #         isCompleteReading = True
    #     except Exception as e:
    #         self.log(f"Error while extracting instruction: {e}", "Error", "error")
    #         self.log(f"Input: {input}", "Error", "error")
    #         isCompleteReading = False

    #     if not isCompleteReading:
    #         self.current_status["servo"] = ServoDegree
    #         self.current_status["conv"]["mode"] = ConvState
    #         self.current_status["conv"]["speed"] = ConvSpeed
    #     else:
    #         self.current_status["servo"] = ServoDegree
    #         self.current_status["conv"]["mode"] = ConvState
    #         self.current_status["conv"]["speed"] = ConvSpeed
    #     return f"{instruction} {servo_info}, {conveyor_info}"



if __name__ == "__main__":
    seri_mane = SeriMane()  
    if seri_mane.arduino_port:
        try:
            while True:
                user_input = input("Enter a message to send to Arduino (or 'exit' to quit): ")
                if user_input.lower() == 'exit':
                    break
                seri_mane.sendMessageToArduino(user_input)
        except KeyboardInterrupt:
            pass
        finally:
            seri_mane.closeConnection()
