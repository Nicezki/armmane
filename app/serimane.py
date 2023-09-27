import serial
import serial.tools.list_ports
import threading
from loguru import logger
import platform
import RPi.GPIO as GPIO
import time


class SeriMane:
    def __init__(self, sysmane):
        self.sysmane = sysmane
        self.current_status = {
            "port" : None,
            "ready" : False,
            "busy" : False,
            'servo' : [0,0,0,0,0,0],
            'conv' : {
                'mode' : [0,0],
                'speed' : [0,0]
            },
            'sensor' : {
                'init' : None,
                'available' : False,
                'value' : False
            },
            "statuscode" : "PS00D000S01D000S02D000S03D000S04D000S05D000C0M0S000C1M0S000",
            "instruction" : None,
            "status" : "Initualizing",
            "message" : "Initualizing Arduino connection"
        }
        self.sensor = None
        self.arduino_port = None
        self.arduino = None
        while not self.arduino_port and self.arduino is None:
            self.initArduinoPort()
            time.sleep(1)


        self.receive_thread = threading.Thread(target=self.receiveMessages)
        # self.receive_thread = threading.Thread(counter=self.timeCount)
        self.receive_thread.daemon = True 
        self.receive_thread.start()
        # Initialize GPIO for the obstacle sensor
        self.sensor_pin = 17  # Use the GPIO number, not the physical pin number
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.sensor_pin, GPIO.IN)
        self.prepare()
        

    def initArduinoPort(self):
        self.arduino_port = self.findArduinoPort()
        if self.arduino_port:
            self.log("Arduino found on port: " + str(self.arduino_port), "Found", "success")
            self.log("Connecting to Arduino with baudrate: " + str(self.sysmane.app_config.get("serial_buadrate")), "Connecting", "debug")
            self.arduino = serial.Serial(self.arduino_port, self.sysmane.app_config.get("serial_buadrate"), timeout=1)   
            self.log("Connected to Arduino", "Connected", "success")
        else:
            self.log("Arduino not found Trying again in 1 second", "Not found", "warning")
            # Retry to find Arduino
            self.arduino = None

    def prepare(self):
        self.checkCurrentState()
        self.checkBusy()
        # Start a thread for obstacle detection
        self.obstacle_thread = threading.Thread(target=self.detectObstacle)
        self.obstacle_thread.daemon = True
        self.obstacle_thread.start()
        self.sensor_thread = threading.Thread(target=self.timeCount)
        self.sensor_thread.daemon = True
        self.sensor_thread.start()

    def timeCount(self):
        time.sleep(5)
        if self.current_status["sensor"]["init"] != True:
            time.sleep(5)
            self.log("No sensor found, please find one for me pretty please >,< ")
            self.current_status["sensor"]["init"] == True
        else:
            self.sensor_thread.join()
        
    def detectObstacle(self):
        while True:
            # Read the digital value from the obstacle sensor
            if self.current_status["sensor"]["init"] == None or self.current_status["sensor"]["init"] == True :
                counterout = 0
                sensor_value = GPIO.input(self.sensor_pin)
                if sensor_value == GPIO.HIGH:
                    self.log("No obstacle detected")
                    self.current_status["sensor"]["value"] = False
                    counterout = counterout+1
                    if counterout == 10:
                        counterout = 0
                        self.current_status["sensor"]["init"] = False
                        self.sensor_thread = threading.Thread(target=self.timeCount)
                        self.sensor_thread.daemon = True
                        self.sensor_thread.start()
                else:
                    self.log("Obstacle detected")
                    self.current_status["sensor"]["init"] = True 
                    self.current_status["sensor"]["available"] = True
                    self.current_status["sensor"]["value"] = True
                time.sleep(0.5)  # Adjust the sleep time as needed
            else:
                logger.error("No sensor")
                time.sleep(0.5)
            
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
        if self.arduino:
            if self.current_status["busy"]:
                self.log("Arduino is busy, cannot send message.", "Busy", "error")
                return "busy", self.current_status
            if self.arduino:
                self.log(f"Sending message to Arduino: {message}", "Sending")
                try:
                    self.arduino.write(message.encode())  # Send the message to Arduino
                    self.log(f"Message sent to Arduino: {message}", "Sent", "success")
                    return "ok", self.current_status
                except Exception as e:
                    self.log(f"Error while sending message to Arduino: {e}", "Error", "error")
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
                return "error", self.current_status
        else:
            self.log("Arduino not found, cannot send message.", "Error", "error")
            return "error", self.current_status

    def receiveMessages(self):
        while True:
            if self.arduino:
                line = str(self.arduino.readline().decode().strip())
                # If the line is empty, skip it
                if not line:
                    continue
                # If the line is "Ready!", set isArduinoReady to True
                if line == "Ready!":
                    self.current_status["ready"] = True
                    self.log("Arduino is ready.", "Ready", "success")
                    self.checkCurrentState()
                    self.checkBusy()
                    continue
                if line == "PB":
                    self.current_status["busy"] = True
                    self.log("Arduino is busy.", "Busy", "warning")
                    continue
                if line == "POK":
                    self.current_status["ready"] = True
                    self.current_status["busy"] = False
                    self.log("Arduino is not busy.", "Ready", "success")
                    continue
                if line.startswith("PS") or line.startswith("PF"):
                    self.current_status["instruction"] = self.extractInstruction(line)
                    self.current_status["statuscode"] = line
                else: self.log(f"{line}", "Arduino", "debug")
            else:
                self.log("Arduino not found, cannot receive message.", "Error", "trace")
                return None
                
    def checkCurrentState(self):
        self.sendMessageToArduino("PC")
        
    def checkBusy(self):
        self.sendMessageToArduino("PB")

    def piInstruction(self, action):
        instruction = self.sysmane.app_config.get("instructions")
        # The data look like this 
        # # {
        # "R": {
        #     "step": [
        #         "COV01", "COV11", "S00D080", "S01D075", "S02D080", "S03D075", "S04D000", "S05D040", "DPS001"
        #     ]
        # },
        # "preGrip": {
        #     "step": [
        #         "COV01", "COV11", "S00D080", "S01D075", "S02D020", "S03D030", "S04D000", "S05D040", "DPS001"
        #     ]
        # }
        # }
        #

        #Check if the action is in the instruction list if not return error
        if action not in instruction:
            self.log(f"Action {action} not found in instruction list", "Error", "error")
            return None
        

        # We need to convert the instruction to old format
        # The old format look like this
        # COV01>COV11>S00D080>S01D075>S02D080>S03D075>S04D000>S05D040>DPS001 and add >END at the end

        # Convert to old format
        step = instruction[action]["step"]
        old_format = ">".join(step) + ">END"
        
        # Send the instruction to Arduino with PX(Instruction)
        self.sendMessageToArduino("PX" + old_format)
        self.log(f"Instruction sent: {old_format}")


    def setServo(self, servo, degree):
        # Check if the servo is in range
        if servo < 0 or servo > int(self.sysmane.app_config.get("servo_count")):
            self.log(f"Servo {servo} not in range (0, {self.sysmane.app_config.get('servo_count')})", "Error", "error")
            return None

        # Check if the degree is in range (min, max)
        if degree < int(self.sysmane.app_config.get("servo_min_degree")) or degree > int(self.sysmane.app_config.get("servo_max_degree")):
            self.log(f"Degree {degree} not in range ({self.sysmane.app_config.get('servo_min_degree')}, {self.sysmane.app_config.get('servo_max_degree')})", "Error", "error")
            return None

        # convert the degree to 3 digits
        degree = str(degree).zfill(3)

        # convert the servo to 2 digits
        servo = str(servo).zfill(2)

        # Send the instruction to Arduino with PIS(Servo)D(Degree)
        self.sendMessageToArduino(f"PIS{servo}D{degree}")

    def setConveyor(self, conveyor, mode=None, speed=None):
        if mode is None and speed is None:
            self.log(f"Conveyor {conveyor} is not set", "Error", "error")
            return None
        if mode is None:
            mode = self.current_status["conv"]["mode"][conveyor]
        if speed is None:
            speed = self.current_status["conv"]["speed"][conveyor]
            
        # Check if the conveyor is in range
        if conveyor < 0 or conveyor > int(self.sysmane.app_config.get("conveyor_count")):
            self.log(f"Conveyor {conveyor} not in range (0, {self.sysmane.app_config.get('conveyor_count')})", "Error", "error")
            return None
        
        #Format CXY where X is conveyor number and Y is mode
        # Check if the mode is in range (0, 1, 2)
        if mode < 0 or mode > 2:
            self.log(f"Mode {mode} not in range (0, 1, 2)", "Error", "error")
            return None
        
        if speed <0: speed = 0
        if speed > 255: speed = 255
         
        
        # convert the mode to 1 digits
        mode = str(mode).zfill(1)

        # convert the conveyor to 1 digits
        conveyor = str(conveyor).zfill(1)

        # Send the instruction to Arduino with PIC(Conveyor)(Mode)
        self.sendMessageToArduino(f"PIC{conveyor}M{mode}S{str(speed).zfill(3)}")

    def resetServo(self):
        self.piInstruction("R")

    def closeConnection(self):
        if self.arduino:
            self.arduino.close()
            self.log("Serial connection to Arduino closed.", "Closed", "info")

    def extractInstruction(self, input):
        Mode = 0
        ServoDegree = [0, 0, 0, 0, 0, 0]
        ConvState = [0, 0]
        ConvSpeed = [0, 0]

        # Split input by 'S' to separate servo data
        servo_data_parts = input.split('S')[1:7]  # Skip the first element

        for i, data_part in enumerate(servo_data_parts):
            servo_number = i
            # Locate the 'D' separator within each servo data part
            d_index = data_part.find('D')
            if d_index != -1:  # Check if 'D' separator was found
                degree_str = data_part[d_index + 1:d_index + 4]  # Extract 3 characters for the degree part
                if degree_str:
                    degree = int(degree_str)
                    ServoDegree[servo_number] = degree
                else:
                    # Handle the case where degree_str is empty or not a valid integer
                    ServoDegree[servo_number] = 0  # or some default value, depending on your requirements

        # Split input by 'C' to separate conveyor data
        #C0M{mode}S{speed}C1M{mode}S{speed}
        # Mode is 1 digit start from 0 to 2
        # Speed is 3 digit start from 000 to 255
        # input.split('C') return ['PS00D000S01D000S02D000S03D000S04D000S05D000', '0M0S000', '1M0S000']
        # print (input.split('C'))
        # print (f"CVState0: {input.split('C')[1][2:3]} | CVSpeed0: {input.split('C')[1][4:7]} | CVState1: {input.split('C')[2][2:3]} | CVSpeed1: {input.split('C')[2][4:7]}")
        ConvState[0] = int(input.split('C')[1][2:3])
        ConvSpeed[0] = int(input.split('C')[1][4:7])
        ConvState[1] = int(input.split('C')[2][2:3])
        ConvSpeed[1] = int(input.split('C')[2][4:7])
        # self.log(f"C0 is {ConvState[0]} at speed {ConvSpeed[0]}| C1 is {ConvState[1]} at speed {ConvSpeed[1]}", "Instruction", "debug")

        if input.startswith("PS"):
            Mode = 1
        elif input.startswith("PF"):
            Mode = 2

        instruction = f"[Instruction] {'Smooth' if Mode == 1 else 'Force'}"
        servo_info = ', '.join([f"S{i} at {degree} degree" for i, degree in enumerate(ServoDegree)])
        conveyor_info = ', '.join([f"Conveyor {i} is {'forward' if mode == 1 else 'stop' if mode == 0 else 'backward'}" for i, mode in enumerate(ConvState)])
        self.current_status["servo"] = ServoDegree
        self.current_status["conv"]["mode"] = ConvState
        self.current_status["conv"]["speed"] = ConvSpeed
        return f"{instruction} {servo_info}, {conveyor_info}"


        

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
