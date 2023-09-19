# Import packages
import os
import json
import platform
import cv2
import numpy as np
import sys
import time
from threading import Thread
import importlib.util
from loguru import logger

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
    def __init__(self,resolution=(640,480),framerate=30):
        # Initialize the PiCamera and the camera image stream
        self.stream = cv2.VideoCapture(0)
        if self.stream.isOpened():
            logger.info("Hi")
        else:
            logger.error("No camera found")
        
        ret = self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ret = self.stream.set(3,resolution[0])
        ret = self.stream.set(4,resolution[1])
            
        # Read first frame from the stream
        (self.grabbed, self.frame) = self.stream.read()

	# Variable to control when the camera is stopped
        self.stopped = False

    def start(self):
	# Start the thread that reads frames from the video stream
        Thread(target=self.update,args=()).start()
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
            (self.grabbed, self.frame) = self.stream.read()

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
            "frame" : None,
            "confident_score" : 0,
            "classes" : "",
            "result_frame" : None,
            "detect_flag" : False,
            "fps" : 0
        }

        self.run()

    def run(self):
         logger.info("TFMane is running")
         self.camera=self.checkAvaiableCamera()
         logger.info("Camara index: {}".format(self.camera))

         if self.camera==[]:
            logger.info("No camera avaliable right now, Please plug in the usb camera or picam ")
           
         else: 
            self.setup()
            self.detect()

    def setup(self):
        logger.info("Loading model: {}".format(self.sysmane.getModelPath(self.sysmane.getCurrentModel())))
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

        if ('StatefulPartitionedCall' in self.outname): # This is a TF2 model
            self.boxes_idx, self.classes_idx, self.scores_idx = 1, 3, 0
        else: # This is a TF1 model
            self.boxes_idx, self.classes_idx, self.scores_idx = 0, 1, 2
    
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
    
    def getcurrentStatus(self):
        return self.current_status
    
    def closeDetect(self):
        self.close = True
        
    def detect(self):
        self.close = False
        self.video = VideoStream(resolution=(self.imageWidth,self.imageHeight),framerate=self.framerate).start()
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
            self.current_status['frame'] = frame
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
            
            # Loop over all detections and draw detection box if confidence is above minimum threshold
            for i in range(len(scores)):
                if ((scores[i] >  self.model_config.get("config","min_conf_threshold")) and (scores[i] <= 1.0)):
                    self.current_status['detect_flag'] = True
                    # Get bounding box coordinates and draw box
                    # Interpreter can return coordinates that are outside of image dimensions, need to force them to be within image using max() and min()
                    ymin = int(max(1,(boxes[i][0] * self.imageHeight)))
                    xmin = int(max(1,(boxes[i][1] * self.imageWidth)))
                    ymax = int(min(self.imageHeight,(boxes[i][2] * self.imageHeight)))
                    xmax = int(min(self.imageWidth,(boxes[i][3] * self.imageWidth)))
                    
                    cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)

                    # Draw label
                    object_name = self.labels[int(classes[i])] # Look up object name from "labels" array using class index
                    self.current_status['classes'] = object_name
                    persent_scores  = int(scores[i]*100)# 0.72 to 72%'
                    self.current_status['confident_score'] = persent_scores
                    label = '%s: %d%%' % (object_name, persent_scores) # Example: 'person: 72%'
                    labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
                    label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
                    cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
                    cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text
                
                else:
                    self.current_status['detect_flag'] = False

            # Calculate framerate
            t2 = cv2.getTickCount()
            time1 = (t2-t1)/freq
            frame_rate_calc= 1/time1
            self.current_status['fps'] = frame_rate_calc

            # Draw framerate in corner of frame
            cv2.putText(frame,'FPS: {0:.2f}'.format(frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)
            self.current_status['result_frame'] = frame

            # All the results have been drawn on the frame, so it's time to display it.
            cv2.imshow('Object detector', frame)

            # Press 'q' to quit
            if cv2.waitKey(1) == ord('q'):
            #f self.close :
                break
        # Clean up
        cv2.destroyAllWindows()
        self.video.stop()
