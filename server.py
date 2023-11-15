# Run the server by typing this command in the terminal:
# python -m uvicorn server:app --reload
# For local testing, use
# python -m uvicorn server:app --reload --host 0.0.0.0 --port 5000 --ssl-keyfile=./certs/site-key.pem --ssl-certfile=./certs/site-cert.pem  
# python -m uvicorn server:app --host 0.0.0.0 --port 5000 --ssl-keyfile=./certs/site-key.pem --ssl-certfile=./certs/site-cert.pem 



from app import armmane
from app import sysmane
from app import serimane
from app import TFmane
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from loguru import logger
import json
import copy
import cv2
# SSE
import asyncio
from sse_starlette.sse import EventSourceResponse
from starlette.responses import StreamingResponse
import sys
import time




port = 8000

STREAM_DELAY = 1  # second
RETRY_TIMEOUT = 15000  # milisecond


description = """
ArmMane is a Robot Arm Management System that can use to control robot arm

## Model
- List all models: `/model`
- Set current model: `/model/{model_name}/set`
- Get current model config: `/model/{model_name}/config`
"""

tags_metadata = [
    {
        "name": "Model",
        "description": "Model management",
    },
    {
        "name": "Config",
        "description": "Config management",
    },
    {
        "name": "Status",
        "description": "Status management",
    },
    {
        "name": "Command",
        "description": "Command management",
    },
    {
        "name": "Info",
        "description": "Info management",
    },
    {
        "name": "Server Sent Event",
        "description": "Server Sent Event management",
    }
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="ArmMane",
    description=description,
    summary="ArmMane is a Robot Arm Management System that can use to control robot arm",
    version="0.0.1",
    contact={
        "name": "RMUTT Computer Engineering"
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    
)
#CORS
origins = [
    'http://localhost',
    'http://localhost:8080',
    'https://design.nicezki.com',
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

sys = sysmane.SysMane()
seri = serimane.SeriMane(sys)
tmn = TFmane.TFMane(sys)
amn = armmane.ArmMane(sys, seri,tmn)


@app.get("/info", tags=["Info"])
async def root():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "model": {
                "current_path": sys.getCurrentPath(),
                "current_model": sys.getCurrentModel(),
                "current_model_config": sys.getCurrentModelConfig().getAll(),
                "current_model_path": sys.getModelPath(sys.getCurrentModel()),
                "models": sys.listModelFolder()
            }
        }
    )


@app.get("/config", tags=["Config"], description="Return user config data used in ArmMane")
async def config():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return config",
            "config": sys.app_config.getAll()
        }
    )

@app.get("/config/reload", tags=["Config"], description="Reload user config data used in ArmMane")
async def config_reload():
    sys.reloadConfig()
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Reload config",
            "config": sys.app_config.getAll()
        }
    )


@app.get("/config/currentmodel", tags=["Config Deprecated"], description="Set model that will be used in ArmMane object detection")
@app.post("/config/currentmodel/{key}", tags=["Config"], description="Set model that will be used in ArmMane object detection")
async def config_currentmodel(key: str):
    # Check if key is in list of models
    if key not in sys.listModelFolder():
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Model not found"
            }
        )
    sys.setCurrentModel(key)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set current model to {}".format(key)
        }
    )


@app.get("/model/{model_name}/config", tags=["Model"], description="Return config of the model")
async def model_config(model_name: str):
    # Check if model_name is in list of models
    if model_name not in sys.listModelFolder():
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Model not found"
            }
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return config of {}".format(model_name),
            "config": sys.getModelConfig(model_name).getAll()
        }
    )


@app.get("/status/arm", tags=["Status"], description="Return current status of arm ")
async def status_arm():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return status of arm",
            "status_arm": amn.getCurrentStatus()
        }
    )
@app.get("/status/seri", tags=["Status"], description="Return current status of seri like servo angle, conveyor mode, etc.")
async def status_seri():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return status of seri",
            "status_seri": seri.getCurrentStatus()
        }
    )

@app.get("/status/prediction", tags=["Status"], description="Return current status of prediction confident, class, fps.")
async def status_prediction():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return status of predict",
            "status_prediction": sys.getCurrentResult()
        }
    )

@app.get("/status/alert", tags=["Status"], description="Return current alert status of all system.")
async def status_alert():
    # Get alert from all class (arm, seri, tf) by calling method getAlert()
    alert = {
        "arm": amn.getAlert(),
        "seri": seri.getAlert(),
        "tf": tmn.getAlert()
    }
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return status of alert",
            "status_alert": alert
        }
    )

    
@app.get("/command/servo/{servo}/{angle}", tags=["Command Deprecated"], description="Set servo to desired angle")
@app.post("/command/servo/{servo}/{angle}", tags=["Command"], description="Set servo to desired angle")
async def command_servo(servo: int, angle: int):
    # Check if servo is less than 0 or more than servo_count
    if servo < 0 or servo > int(sys.app_config.get("servo_count")):
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Servo must be between 0 and {}".format(sys.app_config.get("servo_count"))
            }
        )
    if angle < int(sys.app_config.get("servo_min_degree")) or angle > int(sys.app_config.get("servo_max_degree")):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Angle must be between {} and {}".format(sys.app_config.get("servo_min_degree"), sys.app_config.get("servo_max_degree"))
            }
        )
    seri.setSmoothServo(servo, angle)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set servo {} to {}".format(servo, angle)
        }
    )


@app.get("/command/conv/{conv}/{mode}/{speed}", tags=["Command Deprecated"], description="Set conveyor to desired mode with speed")
@app.post("/command/conv/{conv}/{mode}/{speed}", tags=["Command"], description="Set conveyor to desired mode with speed")
async def command_conv(conv: int, mode: int = 0, speed: int = 255):
    if mode == -1 and speed == -1:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Mode or speed must be set"
            }
        )
    
    if mode == -1:
        seri.setConveyor(conveyor=conv, speed=speed)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Set conv {} to speed {}".format(conv, speed)
            }
        )
    
    if speed == -1:
        seri.setConveyor(conveyor=conv, mode=mode)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Set conv {} to mode {}".format(conv, mode)
            }
        )

    # Check if conv is less than 0 or more than conveyor_count
    if conv < 0 or conv > int(sys.app_config.get("conveyor_count")):
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Conv not found"
            }
        )
    if mode not in [0, 1, 2]:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Mode must be 0, 1 or 2"
            }
        )
    if speed < 0 or speed > 255:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Speed must be between 0 and 255"
            }
        )
    seri.setConveyor(conv, mode, speed)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set conv {} to {} with speed {}".format(conv, mode, speed)
        }
    )

@app.get("/command/sorting/{current_type}", tags=["Command Deprecated"], description="Set sorting type of the arm")
@app.post("/command/sorting/{current_type}", tags=["Command"], description="Set sorting type of the arm")
async def change_type(current_type: int = 0):
      amn.setSorting(current_type)
      return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Set sorting to {}".format(current_type)
            }
      )
    
@app.get("/command/preset/{preset}", tags=["Command Deprecated"], description="Run the preset instruction to control the arm")
@app.post("/command/preset/{preset}", tags=["Command"], description="Run the preset instruction to control the arm")
async def command_preset(preset: str):
    # Check if preset is in list of instruction
    if preset not in sys.app_config.get("instructions"):
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Preset not found"
            }
        )
    seri.piInstructionPreset(preset)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set preset {}".format(preset)
        }
    )


@app.get("/command/emergency", tags=["Command Deprecated"], description="Stop the arm immediately")
@app.post("/command/emergency", tags=["Command"], description="Stop the arm immediately")
async def command_emergency():
    seri.setEmergency(True)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set emergency"
        }
    )


@app.get("/command/unlock", tags=["Command Deprecated"], description="Unlock the arm after emergency")
@app.post("/command/unlock", tags=["Command"], description="Unlock the arm after emergency")
async def command_unlock():
    seri.setEmergency(False)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set unlock"
        }
    )

    
        


@app.post("/mode/{mode}", tags=["Status"], description="Set mode of arm (manual or auto)")
async def mode(mode: str):
    # If mode is not manual or auto
    if mode not in ["manual", "auto"]:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Mode must be manual or auto"
            }
        )
    # Set mode
    amn.setMode(mode)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set mode to {}".format(mode)
        }
    )

@app.post("/camera/start", tags=["Status"], description="Start camera")
async def camera_start():
    # Start camera
    result = tmn.startCamera()
    # If false, camera is not available
    if not result:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Camera not available"
            }
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Start camera {}".format(tmn.current_status['current_camera'])
        }
    )
    

@app.post("/camera/stop", tags=["Status"], description="Stop camera")
async def camera_stop():
    # Stop camera
    tmn.stopCamera()
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Stop camera {}".format(tmn.current_status['current_camera'])
        }
    )




@app.post("/camera/{id}", tags=["Status"], description="Set camera ID to use")
async def camera(id: int):
    # If camera is not in list of cameras in tfm.camera_list
    if id not in tmn.camera_list:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Camera not found"
            }
        )
    # Set camera
    result = tmn.switchCamera(id)
    #If false, camera is not available
    if not result:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Camera not available"
            }
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set camera to {}".format(id)
        }
    )

@app.get ("/camera", tags=["Status"], description="Return current availablecamera ID and name") 
async def camera():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return current available camera",
            "camera": tmn.getCamerList()
        }
    )

@app.post("/flag/not_stop_camera/toggle", tags=["Status"], description="Toggle not_stop_camera flag")
async def flag_not_stop_camera_toggle():
    # Toggle not_stop_camera flag
    amn.status["flag"]["not_stop_camera"] = not amn.status["flag"]["not_stop_camera"]
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Toggle not_stop_camera to {}".format(amn.status["flag"]["not_stop_camera"])
        }
    )

@app.post("/flag/not_stop_camera/{status}", tags=["Status"], description="Set not_stop_camera flag to true or false")
async def flag_not_stop_camera(status: bool):
    # Set not_stop_camera flag
    amn.status["flag"]["not_stop_camera"] = status
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set not_stop_camera to {}".format(status)
        }
    )





@app.post("/detect/start", tags=["Status"], description="Start object detection")
async def detect_start():
    # Check if camera is available
    if not tmn.video:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Camera not available"
            }
        )
    # Start object detection
    tmn.startDetect()
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Start object detection"
        }
    )

@app.post("/detect/stop", tags=["Status"], description="Stop object detection")
async def detect_stop():
    # Stop object detection
    tmn.stopDetect()
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Stop object detection"
        }
    )


@app.post("/item/{box}/{item}", tags=["Status"], description="Set item of box")
async def item(box: int, item: int):
    # armmane.py -> setItem
    # Check if box is less than 0 or more than box_count
    if box < 1 or box > int(sys.app_config.get("box_count")):
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Box " + str(box) + " not found (Range 1 - " + str(sys.app_config.get("box_count")) + ")"
            }
        )
    if item < 0 or item > int(sys.app_config.get("item_max_count")):
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "Item " + str(item) + " not found (Range 0 - " + str(sys.app_config.get("item_max_count")) + ")"
            }
        )
    amn.setItem(box, item)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set item of box {} to {}".format(box, item)
        }
    )



async def event_generator(request: Request):
    last_seri_status = {}
    last_arm_status = {}
    last_alert_status = {}
    last_pred_status = {}
    yield {
        # Send connected message to client
        "data": json.dumps({"status": "connected"})
    }
    while True:
        # If client closes connection, stop sending events
        if await request.is_disconnected():
            break
        # Check if status changed
        current_seri_status = seri.getCurrentStatus()
        current_arm_status = amn.getCurrentStatus()
        current_pred_status = sys.getCurrentResult()

        alert = {
        "arm": amn.getAlert(),
        "seri": seri.getAlert(),
        "tf": tmn.getAlert()
        }

        current_alert_status = copy.deepcopy(alert)




        # print("current_status")
        # print(current_status['servo'])
        # print("last_status")
        # print(last_status['servo'])
        
        # Compare individual keys and values
        if last_alert_status != current_alert_status:
            # If client reconnects or status changes, send current_status to client
            last_alert_status = copy.deepcopy(current_alert_status)
            yield {
                "event": "alert_status",
                "data": json.dumps(current_alert_status)
            }

        if last_seri_status != current_seri_status:
            # If client reconnects or status changes, send current_seri_status to client
            last_seri_status = copy.deepcopy(current_seri_status)
            yield {
                "event": "seri_status",
                "data": json.dumps(current_seri_status)
            }
        if last_arm_status != current_arm_status:
            # If client reconnects or status changes, send current_arm_status to client
            last_arm_status = copy.deepcopy(current_arm_status)
            yield {
                "event": "arm_status",
                "data": json.dumps(current_arm_status)
            }

        if last_pred_status != current_pred_status:
            # If client reconnects or status changes, send current_pred_status to client
            last_pred_status = copy.deepcopy(current_pred_status)
            yield {
                "event": "prediction",
                "data": json.dumps(current_pred_status)
            }

        await asyncio.sleep(0.1)


@app.get('/sse/status', tags=["Server Sent Event"], description="Server Sent Event to send arm status to client")
async def sse_status_stream(request: Request):
    return EventSourceResponse(event_generator(request))

# Run the server by typing this command in the terminal:
# python -m uvicorn server:app --reload


@app.get("/stream/video", tags=["StreamingResponse"], description="Better way to get the video stream from ARMMANE camera")
async def get_video_stream():
    def generate():
        while True:
            # If camera is not available, use no_camera_image (in config) instead
            if not tmn.video:
                frame = cv2.imread(sys.app_config.get("no_camera_image"))
                # encode the frame in JPEG format
                (flag, encodedImage) = cv2.imencode(".jpg", frame)
                # ensure the frame was successfully encoded
                if not flag:
                    continue
                # yield the output frame in the byte format
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                    bytearray(encodedImage) + b'\r\n')
                time.sleep(5)
                continue


            frame = tmn.video.read()

            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            # ensure the frame was successfully encoded
            if not flag:
                continue
            # yield the output frame in the byte format
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                bytearray(encodedImage) + b'\r\n')
            
            time.sleep(0.2)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/stream/video2", tags=["StreamingResponse"], description="Better way to get the video stream from ARMMANE camera (with prediction)")
async def get_video_stream():
    def generate():
        while True:
            # If camera is not available, use no_camera_image (in config) instead
            # if not tmn.video:
            if tmn.current_status['camera_running'] == False:
                frame = cv2.imread(sys.app_config.get("pause_camera_image"))
                # encode the frame in JPEG format
                (flag, encodedImage) = cv2.imencode(".jpg", frame)
                # ensure the frame was successfully encoded
                if not flag:
                    continue
                # yield the output frame in the byte format
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                    bytearray(encodedImage) + b'\r\n')
                time.sleep(5)
                continue


            if not tmn.video:
                frame = cv2.imread(sys.app_config.get("no_camera_image"))
                # encode the frame in JPEG format
                (flag, encodedImage) = cv2.imencode(".jpg", frame)
                # ensure the frame was successfully encoded
                if not flag:
                    continue
                # yield the output frame in the byte format
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                    bytearray(encodedImage) + b'\r\n')
                time.sleep(5)
                continue
        
            # t1 = cv2.getTickCount()
            frame = tmn.video.read()

            # From tfm:
            # self.current_status['box'] = {
            #     "box-1": {
            #         "xmin": xmin,
            #         "ymin": ymin,
            #         "xmax": xmax,
            #         "ymax": ymax,
            #         "label": label,
            #         "labelSize": labelSize,
            #         "baseLine": baseLine,
            #         "label_ymin": label_ymin,
            #         "object_name": object_name,
            #         "persent_scores": persent_scores
            #     },
            #     "box-2": {
            #    ...
            #     }
            

            status = sys.getCurrentResult()
            box = status['box']

            # Add box to frame if box is not empty
            if box:
                for key, value in box.items():
                    xmin = value['xmin']
                    ymin = value['ymin']
                    xmax = value['xmax']
                    ymax = value['ymax']
                    label = value['label']
                    labelSize = value['labelSize']
                    baseLine = value['baseLine']
                    label_ymin = value['label_ymin']
                    object_name = value['object_name']
                    persent_scores = value['persent_scores']
                    label = '%s: %d%%' % (object_name, persent_scores)
                    # Draw box
                    # cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)
                    #cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
                    #cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text

                    # Draw box
                    cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)
                    cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
                    cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)


            # Draw Prediction FPS
            cv2.putText(frame,'PFPS: {0:.2f}'.format(status['fps']),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)
            
            # Draw Real FPS
            # Calculate framerate
            # freq = cv2.getTickFrequency()

            # t2 = cv2.getTickCount()
            # time1 = (t2-t1)/freq
            # frame_rate_calc= 1/time1
            # cv2.putText(frame,'RFPS: {0:.2f}'.format(frame_rate_calc),(30,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)        
                    

            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            # ensure the frame was successfully encoded
            if not flag:
                continue
            # yield the output frame in the byte format
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                bytearray(encodedImage) + b'\r\n')
            
            time.sleep(0.4)
            
            
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")