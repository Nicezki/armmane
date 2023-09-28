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

        self.stream = CamGear(source=device, time_delay = 0, logging = True).start()
            
        # Read first frame from the stream
        self.frame = self.stream.read()

	# Variable to control when the camera is stopped
        self.stopped = False

    def __del__(self):
        self.stream.release()
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
                self.stream.release()
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
        self.camera =[]

        self.current_status = {
            "current_result": None,
            "confident_score" : 0,
            "current_classes" : "",
            "detect_flag" : False,
            "fps" : 0,
            "box" : None,
        }

        self.setup()


    def setupCamera(self):
        debugrun = True
        if debugrun:
            # If platform is not linux, then use the default camera
            if system_info != 'Linux':
                self.camera = [1] 
            else:
                self.camera = [0]
        else:
            self.camera=self.checkAvaiableCamera()
            
        logger.info("Camara index: {}".format(self.camera))

        if self.camera==[]:
            logger.info("No camera avaliable right now, Please plug in the usb camera or picam ")
            return False
        else:
            self.video = VideoStream(resolution=(self.imageWidth,self.imageHeight),framerate=self.framerate,device=self.camera[0]).start()
            return True
        
    def setupModel(self):
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

    def setupThread(self):
        self.detect_thread = threading.Thread(target=self.detect)
        self.detect_thread.daemon = True
        self.detect_thread.start()


    # When destroy the object, close the camera
    def __del__(self):
        if self.video is not None:
            self.video.stop()
            logger.info("[TFMaid] Detect that video is running,  So now It's been closed")
        if self.interpreter is not None:
            self.interpreter.close()
            logger.info("[TFMaid] Detect that interpreter is running,  So now It's been closed")
        if self.camera is not None:
            self.camera.release()
            logger.info("[TFMaid] Detect that camera is running,  So now It's been closed")


        
        

    def setup(self):
        logger.info("[TFMaid] setting up")
        self.system_info = platform.system()
        logger.info("[TFMaid] system_info: {}".format(self.system_info))
        # Setup camera
        camera_status = self.setupCamera()
        if not camera_status:
            logger.info("[TFMaid] Camera is not ready, please check the camera")
            return False

        self.setupModel()
        self.setupCamera()
        self.setupThread()
        logger.info("[TFMaid] setting up completed")
    
    
    def checkAvaiableCamera(self):
        # checks the first 10 indexes.
        index = 0
        arr = []
        i = 10
        while i > 0:
            logger.info("Trying to open camera index: {}".format(index))
            cap = cv2.VideoCapture(index)
            if cap.read()[0]:
                arr.append(index)
                cap.release()
            index += 1
            i -= 1
        return arr
    
    # def closeDetect(self):
    #     if self.close:
    #         return True
    #     return False
        
    def detect(self):
        self.close = False
        logger.info("[TFMaid] Detecting")
        # Initialize frame rate calculation
        frame_rate_calc = 1
        freq = cv2.getTickFrequency()
        # Initialize video stream

        #for frame1 in camera.capture_continuous(rawCapture, format="bgr",use_video_port=True):
        while True:

            # Start timer (for calculating frame rate)
            t1 = cv2.getTickCount()

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

            time.sleep(0.33)
            # All the results have been drawn on the frame, so it's time to display it.
            # cv2.imshow('Object detector', frame)
            # Press 'q' to quit
            # if cv2.waitKey(1) == ord('q'):
            #if self.closeDetect():
                # break
        # Clean up
        # destroyAllWindows()
        # self.video.stop()
