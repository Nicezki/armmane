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

import tensorflow as tf


# Define VideoStream class to handle streaming of video from webcam in separate processing thread
class VideoStream:
    """Camera object that controls video streaming from the Picamera"""
    def __init__(self,resolution=(640,480),framerate=30):
        # Initialize the PiCamera and the camera image stream
        # for camera_index in range(3):

        # if self.platform == 'Linux':
        #     pass
        # else:
        #     pass
        self.stream = cv2.VideoCapture(0)
        if self.stream.isOpened():
            # print(f"Raspberry Pi camera is available at path: {camera_path}")
                  # Exit the loop if a working camera is found
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




# class WebcamDetection:
#     def __init__(self):
#         # self.sysmame=sym.SysMane()
#         # self.tfmane = TFMane(self.sysmame.getCurrentModel())
#         self.platformcheck
#         self.interpreter = Interpreter("rmutt_model.tflite")
#         self.interpreter.allocate_tensors()
        
#         # Get model details
#         self.input_details = self.interpreter.get_input_details()
#         self.output_details = self.interpreter.get_output_details()
#         self.height = self.input_details[0]['shape'][1]
#         self.width = self.input_details[0]['shape'][2]
#         self.floating_model = (self.input_details[0]['dtype'] == np.float32)

#         # Check output layer name to determine if this model was created with TF2 or TF1,
#         # because outputs are ordered differently for TF2 and TF1 models
#         self.outname = self.output_details[0]['name']

#         if ('StatefulPartitionedCall' in self.outname): # This is a TF2 model
#             self.boxes_idx, self.classes_idx, self.scores_idx = 1, 3, 0
#         else: # This is a TF1 model
#             self.boxes_idx, self.classes_idx, self.scores_idx = 0, 1, 2
        


#     # Load model 
#     def modelload(self):
#         interpreter = Interpreter(self.tfmane.model)
#         logger.info("Model loaded: {}".format(self.tfmane.model))
#         interpreter.allocate_tensors()
#         return interpreter


#     def platformcheck(self):
#         system_info = platform.system()
#         if system_info == 'Linux':
#             from tflite_runtime.interpreter import Interpreter
#         else: 
#             from tensorflow.lite.python.interpreter import Interpreter
       
#         return system_info
    
#     def closedetect(self):
#         print("HII@@@@")
        


#     def detect(self):

#         print("hi")
#         # Initialize frame rate calculation
#         self.frame_rate_calc = 1
#         self.freq = cv2.getTickFrequency()

#         # Initialize video stream
#         self.video = VideoStream(resolution=(self.imW,self.imH),framerate=30).start()
#         time.sleep(1)

#         #for frame1 in camera.capture_continuous(rawCapture, format="bgr",use_video_port=True):
#         while True:

#             # Start timer (for calculating frame rate)
#             t1 = cv2.getTickCount()

#             # Grab frame from video stream
#             frame1 = self.video.read()

#             # Acquire frame and resize to expected shape [1xHxWx3]
#             frame = frame1.copy()
#             frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             frame_resized = cv2.resize(frame_rgb, (self.width, self.height))
#             input_data = np.expand_dims(frame_resized, axis=0)

#             # Normalize pixel values if using a floating model (i.e. if model is non-quantized)
#             if self.floating_model:
#                 input_data = (np.float32(input_data) - self.tfmane.config.get("input_mean")) / self.tfmane.config.get("input_std")

#             # Perform the actual detection by running the model with the image as input
#             self.interpreter.set_tensor(self.input_details[0]['index'],input_data)
#             self.interpreter.invoke()

#             # Retrieve detection results
#             boxes = self.interpreter.get_tensor(self.output_details[self.boxes_idx]['index'])[0] # Bounding box coordinates of detected objects
#             classes = self.interpreter.get_tensor(self.output_details[self.classes_idx]['index'])[0] # Class index of detected objects
#             scores = self.interpreter.get_tensor(self.output_details[self.scores_idx]['index'])[0] # Confidence of detected objects

#             # Loop over all detections and draw detection box if confidence is above minimum threshold
#             for i in range(len(scores)):
#                 if ((scores[i] > self.tfmane.config.get("min_conf_threshold")) and (scores[i] <= 1.0)):

#                     # Get bounding box coordinates and draw box
#                     # Interpreter can return coordinates that are outside of image dimensions, need to force them to be within image using max() and min()
#                     ymin = int(max(1,(boxes[i][0] * self.imH)))
#                     xmin = int(max(1,(boxes[i][1] * self.imW)))
#                     ymax = int(min(self.imH,(boxes[i][2] * self.imH)))
#                     xmax = int(min(self.imW,(boxes[i][3] * self.imW)))
                    
#                     cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)

#                     # Draw label
#                     object_name = self.labels[int(classes[i])] # Look up object name from "labels" array using class index
#                     label = '%s: %d%%' % (object_name, int(scores[i]*100)) # Example: 'person: 72%'
#                     labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
#                     label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
#                     cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
#                     cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text

#             # Draw framerate in corner of frame
#             cv2.putText(frame,'FPS: {0:.2f}'.format(frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)

#             # All the results have been drawn on the frame, so it's time to display it.
#             cv2.imshow('Object detector', frame)

#             # Calculate framerate
#             t2 = cv2.getTickCount()
#             time1 = (t2-t1)/self.freq
#             frame_rate_calc= 1/time1

#             # Press 'q' to quit
#             if cv2.waitKey(1) == ord('q'):
#                  break
#         # Clean up
#         cv2.destroyAllWindows()
#         self.video.stop()
    
class TFMane:
    def __init__(self, sysmame):

        # configwow = self.model_config.get("config") # Get config
        # configwow = self.model_.get("config", "image_width") # Get config
        # configwow = self.model_config.get() # Get all config

        self.sysmane = sysmame
        self.model_config = self.sysmane.getCurrentModelConfig()
        self.model = self.model_config.get("model_file")
        self.labels = self.model_config.get("model_classes")
        

        self.system_info = None
        self.interpreter = None

        self.imageWidth = self.model_config.get("config","image_width")
        self.imageHeight = self.model_config.get("config","image_height")   
        self.framerate = self.model_config.get("config","framerate")
        self.platform = self.platformCheck()

        self.video = None
        self.run()

    def run(self):
         logger.info("TFMane is running")
         logger.info("Camara index: {}".format(self.checkAvaiableCamera()))
         self.video = VideoStream(resolution=(self.imageWidth,self.imageHeight),framerate=self.framerate).start()
         #self.loadModel()
         self.setup()
         self.detect()

    def setup(self):
        logger.info("Loading model: {}".format(self.sysmane.getModelPath(self.sysmane.getCurrentModel())))
        test = os.path.join(self.sysmane.getFullModelPath(self.sysmane.getCurrentModel()),"rmutt_model.tflite")
        self.interpreter = tf.lite.Interpreter(model_path="rmutt_model.tflite")
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


    def platformCheck(self):
        system_info = platform.system()
        if system_info == 'Linux':
            logger.info("Detected Linux system | Now using tflite_runtime")
            from tflite_runtime.interpreter import Interpreter
        else: 
            logger.info("Detected non-Linux system | Now using tensorflow.lite")
            import tensorflow as tf
            #from tensorflow.lite.python.interpreter import Interpreter
        return system_info
    
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
        
    
    def loadModel(self):
        logger.info("Loading model: {}".format(self.sysmane.getFullModelPath(self.sysmane.getCurrentModel())))
        self.interpreter = tf.lite.Interpreter(self.sysmane.getFullModelPath(self.sysmane.getCurrentModel()))
        self.interpreter.allocate_tensors()
        logger.info("Model loaded: {}".format(self.sysmane.getFullModelPath(self.sysmane.getCurrentModel())))
    

    def detect(self):
        # Initialize frame rate calculation
        self.frame_rate_calc = 1
        self.freq = cv2.getTickFrequency()
        # Initialize video stream


        #for frame1 in camera.capture_continuous(rawCapture, format="bgr",use_video_port=True):
        while True:
            # Start timer (for calculating frame rate)
            t1 = cv2.getTickCount()

            # Grab frame from video stream
            frame1 = self.video.read()

            # Acquire frame and resize to expected shape [1xHxWx3]
            frame = frame1.copy()
            self.sysmane.setCurrentFrame(frame)
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

                    # Get bounding box coordinates and draw box
                    # Interpreter can return coordinates that are outside of image dimensions, need to force them to be within image using max() and min()
                    ymin = int(max(1,(boxes[i][0] * self.imH)))
                    xmin = int(max(1,(boxes[i][1] * self.imW)))
                    ymax = int(min(self.imH,(boxes[i][2] * self.imH)))
                    xmax = int(min(self.imW,(boxes[i][3] * self.imW)))
                    
                    cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)

                    # Draw label
                    object_name = self.labels[int(classes[i])] # Look up object name from "labels" array using class index
                    label = '%s: %d%%' % (object_name, int(scores[i]*100)) # Example: 'person: 72%'
                    labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
                    label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
                    cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
                    cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text

            # Draw framerate in corner of frame
            cv2.putText(frame,'FPS: {0:.2f}'.format(frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)

            # All the results have been drawn on the frame, so it's time to display it.
            cv2.imshow('Object detector', frame)

            # Calculate framerate
            t2 = cv2.getTickCount()
            time1 = (t2-t1)/self.freq
            frame_rate_calc= 1/time1

            # Press 'q' to quit
            if cv2.waitKey(1) == ord('q'):
                break
        # Clean up
        cv2.destroyAllWindows()
        self.video.stop()



if __name__ == "__main__":
    import sysmane
    sysmane = sysmane.SysMane()
    TFMane(sysmane)
