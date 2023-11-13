# Import packages
#pip install -U vidgear
# import os
import json
import platform
import cv2
import base64
import numpy as np
# import sys
import time
import threading
import queue
# import importlib.util
from loguru import logger
from vidgear.gears import CamGear
from pygrabber.dshow_graph import FilterGraph

system_info = platform.system()
if system_info == 'Linux':
    logger.info("Detected Linux system | Now using tflite_runtime")
    from tflite_runtime.interpreter import Interpreter
else: 
    logger.info("Detected non-Linux system | Now using tensorflow.lite")
    from tensorflow.lite.python.interpreter import Interpreter


# Define VideoStream class to handle streaming of video from webcam in separate processing thread
class VideoStream:
    """Camera object that controls video streaming from the Picamera"""
    def __init__(self,resolution=(640,480),framerate=30,device=0):
        # Initialize the PiCamera and the camera image stream
        # self.stream = cv2.VideoCapture(device)
        try:
            self.stream = CamGear(source=device, time_delay = 0, logging = False).start()
        except Exception as e:
            logger.info("Error when open camera: {}".format(e))
            self.stream = None
            return None
            
        # Read first frame from the stream
        self.frame = self.stream.read()

	    # Variable to control when the camera is stopped
        self.stopped = False

    def __del__(self):
        self.stream.stop()
        logger.info("[TFMaid] Detect that video is running,  So now It's been closed")

    def start(self):
	# Start the thread that reads frames from the video stream
        threading.Thread(target=self.update,args=()).start()
        return self

    def update(self):
        # Keep looping indefinitely until the thread is stopped
        while True:
            # If the camera is stopped, stop the thread
            if self.stopped:
                # Close camera resources
                self.stream.stop()
                return

            # Otherwise, grab the next frame from the stream
            currentframe = self.stream.read()

            if currentframe is not None:
                self.frame = currentframe.copy()
            
    def stream(self):
        return self.stream

    def read(self):
	# Return the most recent frame
        return self.frame

    def stop(self):
	# Indicate that the camera and thread should be stopped
        self.stopped = True
    
class TFMane:
    def __init__(self, sysmame):

        self.sysmane = sysmame
        self.model_config = self.sysmane.getCurrentModelConfig()
        self.model = self.model_config.get("model_file")
        self.labels = self.model_config.get("model_classes")
        
        self.system_info = None
        self.interpreter = None

        self.imageWidth = self.model_config.get("config","image_width")
        self.imageHeight = self.model_config.get("config","image_height")   
        self.framerate = self.model_config.get("config","framerate")

        self.video = None
        self.camera_list =[]
        self.camera_name = []

        self.current_status = {
            "current_result": None,
            "confident_score" : 0,
            "current_classes" : "",
            "detect_flag" : False,
            "detect_running" : False,
            "camera_running" : False,
            "current_camera" : 0,
            "fps" : 0,
            "box" : None,
            "alert":{
                "camera_not_working": False,
                "model_not_working": False
            }
        }

        self.setup()
        self.setupDetect()


    def getAlert(self):
        return self.current_status["alert"]
        

    def setupCamera(self):
        debugrun = False
        if debugrun:
            # If platform is not linux, then use the default camera
            if system_info != 'Linux':
                self.camera_list = [1]
                self.camera_name = ["Default Camera"] 
            else:
                self.camera_list = [0]
                self.camera_name = ["Default Camera"]
        else:
            self.camera_list, self.camera_name = self.checkAvaiableCamera()
            
        logger.info("Camara index: {} ({})".format(self.camera_list, self.camera_name))

        if len(self.camera_list) > 0:
            try:
                self.video = VideoStream(resolution=(self.imageWidth,self.imageHeight),framerate=self.framerate,device=self.current_status['current_camera']).start()
                # Try to get a frame to check if the camera is ready
                frame = self.video.read()
                logger.info("Camera is ready")
                self.current_status['alert']['camera_not_working'] = False
                self.current_status['detect_running'] == True
                self.stopCamera()
            except Exception as e:
                logger.info("Error when open camera: {}".format(e))
                self.current_status['alert']['camera_not_working'] = True
                return False
            return True
        else:
            logger.info("No camera avaliable right now, Please plug in the usb camera or picam ")
            self.current_status['alert']['camera_not_working'] = True
            return False
        
    def setupModel(self):
        if self.model is None:
            logger.info("No model avaliable right now, Please choose the model first")
            self.current_status['alert']['model_not_working'] = True
            return False
        if self.interpreter is not None:
            self.interpreter.close()
            logger.info("[TFMaid] Detect that interpreter is running,  So now It's been closed")

        if self.camera_list is None:
            logger.info("[TFMaid] Detect that camera is not ready,  Can't setup model")
            return False
        
        self.interpreter = Interpreter(model_path=self.sysmane.getFullModelPath(self.sysmane.getCurrentModel()))
        self.interpreter.allocate_tensors()
        
        # Get model details
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.height = self.input_details[0]['shape'][1]
        self.width = self.input_details[0]['shape'][2]
        self.floating_model = (self.input_details[0]['dtype'] == np.float32)
        logger.info("Model loaded: {}".format(self.sysmane.getModelPath(self.sysmane.getCurrentModel())))
        logger.info("Height: {} | Width: {}".format(self.height, self.width))
        # Check output layer name to determine if this model was created with TF2 or TF1,
        # because outputs are ordered differently for TF2 and TF1 models
        self.outname = self.output_details[0]['name']

        if ('StatefulPartitionedCall' in self.outname):
            self.boxes_idx, self.classes_idx, self.scores_idx = 1, 3, 0
        else:
            self.boxes_idx, self.classes_idx, self.scores_idx = 0, 1, 2

    # When destroy the object, close the camera
    def __del__(self):
        if self.video is not None:
            self.video.stop()
            logger.info("[TFMaid] Detect that video is running,  So now It's been closed")
            self.video = None
        if self.interpreter is not None:
            self.interpreter.close()
            logger.info("[TFMaid] Detect that interpreter is running,  So now It's been closed")


    def stopDetect(self):
        self.current_status['detect_running'] = False
        self.current_status['detect_flag'] = False
        self.current_status['box'] = None
        self.current_status['current_classes'] = ""
        self.current_status['confident_score'] = 0
        self.current_status['fps'] = 0
        self.current_status['current_result'] = None
        self.sysmane.setCurrentResult(self.current_status)

    def startDetect(self):
        self.current_status['detect_running'] = True
    
    def setupDetect(self):
        detect_thread = threading.Thread(target=self.detect)
        detect_thread.daemon = True
        detect_thread.start()


    def stopCamera(self):
        self.current_status['camera_running'] = False
        self.video.stop()
        self.video = None

    def getCamerList(self):
        return dict(zip(self.camera_list, self.camera_name))

    def switchCamera(self, camera_index):
        if self.video is not None:
            self.video.stop()
            logger.info("[TFMaid] Detect that video is running,  So now It's been closed")
            self.video = None
        try:
            self.video = VideoStream(resolution=(self.imageWidth,self.imageHeight),framerate=self.framerate,device=camera_index).start()
        except Exception as e:
            logger.info("Error when open camera: {}".format(e))
            self.current_status['alert']['camera_not_working'] = True
            return False
        
        self.current_status['current_camera'] = camera_index
        self.current_status['camera_running'] = True
        self.current_status['alert']['camera_not_working'] = False
        return True

    def startCamera(self):
        # Check if the camera is ready first
        if self.video is not None:
            #Check if the camera is running
            if self.current_status['camera_running'] == True:
                logger.info("Camera is already running")
                return True
        while True:
            try:
                self.video = VideoStream(resolution=(self.imageWidth,self.imageHeight),framerate=self.framerate,device=self.current_status['current_camera']).start()
                # Try to get a frame to check if the camera is ready
                frame = self.video.read()
                logger.info("Camera is ready")
                self.current_status['camera_running'] = True
                self.current_status['alert']['camera_not_working'] = False
                break
            except Exception as e:
                logger.info("Error when open camera: {}".format(e))
                logger.info("Retry to open camera in 1 second...")
                self.current_status['alert']['camera_not_working'] = True
                time.sleep(1)
        return True
    
    def setup(self):
        logger.info("[TFMaid] setting up")
        self.system_info = platform.system()
        logger.info("[TFMaid] system_info: {}".format(self.system_info))
        # Setup camera
        camera_status = self.setupCamera()
        if not camera_status:
            logger.info("[TFMaid] Camera is not ready, please check the camera")
            self.current_status['alert']['camera_not_working'] = True
            return False
        else:
            self.setupModel()
            self.current_status['alert']['camera_not_working'] = False
            logger.info("[TFMaid] setting up completed")
            

    def closeDetect(self):
        return self.close
    
    
    # def checkAvaiableCamera(self):
    #     # checks the first 10 indexes.
    #     #If linux, then only scan 1 index
    #     index = 0
    #     arr = []
    #     checkLimit = 10
    #     while index < checkLimit:
    #         logger.info("Checking camera index: {}".format(index))
    #         cap = cv2.VideoCapture(index)
    #         if cap.read()[0]:
    #             arr.append(index)
    #             cap.release()
    #             logger.success("Camera index {} is available".format(index))
    #         else:
    #             logger.warning("Camera index {} is not available".format(index))
    #         index += 1
    #     return arr

    # Return the camera ID and name
    def checkAvaiableCamera(self):
        devices = FilterGraph().get_input_devices()
        logger.info("Checking camera devices: {}".format(devices))
        available_cameras_name = []
        available_cameras_id = []

        for device_index, device_name in enumerate(devices):
            # available_cameras[device_index] = device_name
            available_cameras_name.append(device_name)
            available_cameras_id.append(device_index)
            logger.info("Camera index {} ({}) is available".format(device_index, device_name))
        return available_cameras_id, available_cameras_name

            


    def  detect(self):
        # if self.video is None:
        #     logger.info("[TFMaid] Detect that video is not ready,  So now It's been closed")
        #     return False
        
        self.close = False
        logger.info("[TFMaid] Detecting")
        # Initialize frame rate calculation
        frame_rate_calc = 1
        freq = cv2.getTickFrequency()
        # Initialize video stream

        #for frame1 in camera.capture_continuous(rawCapture, format="bgr",use_video_port=True):
        while True:

            if self.current_status['detect_running'] == False:
                time.sleep(1)
                continue
            
            # Start timer (for calculating frame rate)
            t1 = cv2.getTickCount()

            try:
                # Grab frame from video stream
                frame1 = self.video.read()

                # Acquire frame and resize to expected shape [1xHxWx3]
                frame = frame1.copy()
                # Encode the frame as JPEG
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (self.width, self.height))
                input_data = np.expand_dims(frame_resized, axis=0)

                # Normalize pixel values if using a floating model (i.e. if model is non-quantized)
                if self.floating_model:
                    input_data = (np.float32(input_data) - self.model_config.get("config","input_mean")) /  self.model_config.get("config","input_std")

                # Perform the actual detection by running the model with the image as input
                self.interpreter.set_tensor(self.input_details[0]['index'],input_data)
                self.interpreter.invoke()
                
                # Retrieve detection results
                boxes = self.interpreter.get_tensor(self.output_details[self.boxes_idx]['index'])[0] # Bounding box coordinates of detected objects
                classes = self.interpreter.get_tensor(self.output_details[self.classes_idx]['index'])[0] # Class index of detected objects
                scores = self.interpreter.get_tensor(self.output_details[self.scores_idx]['index'])[0] # Confidence of detected objects
                
                # Remove the old box
                if 'box' in self.current_status and self.current_status['box'] is not None:
                    self.current_status['box'] = None

                # Loop over all detections and draw detection box if confidence is above minimum threshold
                for i in range(len(scores)):
                    if ((scores[i] > self.model_config.get("config","min_conf_threshold")) and (scores[i] <= 1.0)):
                        # Get bounding box coordinates and draw box
                        # Interpreter can return coordinates that are outside of image dimensions, need to force them to be within image using max() and min()
                        self.current_status['detect_flag'] = True
                        ymin = int(max(1,(boxes[i][0] * self.imageHeight)))
                        xmin = int(max(1,(boxes[i][1] * self.imageWidth)))
                        ymax = int(min(self.imageHeight,(boxes[i][2] * self.imageHeight)))
                        xmax = int(min(self.imageWidth,(boxes[i][3] * self.imageWidth)))


                        # # #DEPRECATED : After build 202309290001 - we will use the new way to send the result
                        # # Draw the new box
                        # cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)

                        # Draw label
                        object_name = self.labels[int(classes[i])] # Look up object name from "labels" array using class index
                        self.current_status['current_classes'] = object_name
                        persent_scores  = int(scores[i]*100)# 0.72 to 72%'
                        self.current_status['confident_score'] = persent_scores
                        label = '%s: %d%%' % (object_name, persent_scores) # Example: 'person: 72%'
                        labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
                        label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
                        
                        self.current_status['box'] = {
                            # box-xxx
                            "box-{}".format(i): {
                                    "xmin": xmin,
                                    "ymin": ymin,
                                    "xmax": xmax,
                                    "ymax": ymax,
                                    "label": label,
                                    "labelSize": labelSize,
                                    "baseLine": baseLine,
                                    "label_ymin": label_ymin,
                                    "object_name": object_name,
                                    "persent_scores": persent_scores
                                }
                        }
                        # #DEPRECATED : After build 202309290001 - we will use the new way to send the result
                        # cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
                        # cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text
                
                #Determine if the box is empty
                if 'box' in self.current_status and self.current_status['box'] is None:
                    self.current_status['detect_flag'] = False
                else:
                    self.current_status['detect_flag'] = True
            
            except Exception as e:
                logger.info("Error when detect: {}".format(e))
                logger.info("Maybe camera is offline or disconnected, or you switch the camera")
                self.current_status['alert']['model_not_working'] = True
                self.current_status['detect_flag'] = False
                self.current_status['current_classes'] = ""
                self.current_status['confident_score'] = 0
                self.current_status['fps'] = 0
                self.current_status['current_result'] = None
                self.sysmane.setCurrentResult(self.current_status)
                time.sleep(1)
                continue

            # Calculate framerate
            t2 = cv2.getTickCount()
            time1 = (t2-t1)/freq
            frame_rate_calc= 1/time1
            self.current_status['fps'] = frame_rate_calc


            # #DEPRECATED : After build 202309290001 - we will use the new way to send the result
            # # Draw framerate in corner of frame
            # cv2.putText(frame,'FPS: {0:.2f}'.format(frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)
            # _, png_result = cv2.imencode(".jpg", frame)
            # base64_result = base64.b64encode(png_result).decode("utf-8")
            # self.current_status['current_result'] = base64_result

            self.sysmane.setCurrentResult(self.current_status)

            time.sleep(1)
            # All the results have been drawn on the frame, so it's time to display it.
            # cv2.imshow('Object detector', frame)
            # Press 'q' to quit
            # if cv2.waitKey(1) == ord('q'):
            #if self.closeDetect():
                # break
        # Clean up
        # destroyAllWindows()
        # self.video.stop()

        
