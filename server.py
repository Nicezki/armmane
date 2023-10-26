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


@app.get("/status/arm", tags=["Status"], description="Return current status of arm like servo angle, conveyor mode, etc.")
async def status_arm():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return status of arm",
            "status_arm": seri.getCurrentStatus()
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
    seri.piInstruction(preset)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set preset {}".format(preset)
        }
    )
    
# @app.get("/command/px/{instruction}", tags=["Command Deprecated"], description="Set multi-instruction (ElonX-instruction) to control the arm")
# @app.post("/command/px/{instruction}", tags=["Command"], description="Set multi-instruction (ElonX-instruction) to control the arm")
# async def command_px(instruction: str):
#     seri.sendMessageToArduino("PX" + instruction + ">END")
#     return JSONResponse(
#         status_code=200,
#         content={
#             "status": "success",
#             "message": "Set instruction {}".format(instruction)
#         }
#     )

# @app.get("/command/pi/{instruction}", tags=["Command Deprecated"], description="Set single-instruction (Elon-instruction) to control the arm")
# @app.post("/command/pi/{instruction}", tags=["Command"], description="Set single-instruction (Elon-instruction) to control the arm")
# async def command_pi(instruction: str):
#     seri.sendMessageToArduino("PI" + instruction)
#     return JSONResponse(
#         status_code=200,
#         content={
#             "status": "success",
#             "message": "Set instruction {}".format(instruction)
#         }
#     )
    

# @app.get("/command/reset", tags=["Command Deprecated"], description="Reset arm to default waiting position")
# @app.post("/command/reset", tags=["Command"], description="Reset arm to default waiting position")
# async def command_reset():
#     seri.resetServo()
#     return JSONResponse(
#         status_code=200,
#         content={
#             "status": "success",
#             "message": "Reset arm"
#         }
#     )

@app.get("/mode/{mode}", tags=["Status"], description="Set mode of arm (manual or auto)")
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



async def event_generator(request: Request):
    last_status = {}
    yield {
        # Send connected message to client
        "data": json.dumps({"status": "connected"})
    }
    while True:
        # If client closes connection, stop sending events
        if await request.is_disconnected():
            break
        # Check if status changed
        current_status = seri.getCurrentStatus()
        # print("current_status")
        # print(current_status['servo'])
        # print("last_status")
        # print(last_status['servo'])
        
        # Compare individual keys and values
        if last_status != current_status:
            # If client reconnects or status changes, send current_status to client
            last_status = copy.deepcopy(current_status)
            yield {
                "event": "arm_status",
                "data": json.dumps(current_status)
            }

        await asyncio.sleep(0.1)


@app.get('/sse/status', tags=["Server Sent Event"], description="Server Sent Event to send arm status to client")
async def sse_status_stream(request: Request):
    return EventSourceResponse(event_generator(request))

# Run the server by typing this command in the terminal:
# python -m uvicorn server:app --reload


async def video_generator(request: Request):
    last_status = {}
    yield {
        # Send connected message to client
        "data": json.dumps({"status": "connected"})
    }
    while True:
        # If client closes connection, stop sending events
        if await request.is_disconnected():
            break
        # Check if status changed
        current_status = sys.getCurrentResult()
        
        # Compare individual keys and values
        if last_status != current_status:
            # If client reconnects or status changes, send current_status to client
            last_status = copy.deepcopy(current_status)
            yield {
                "event": "prediction",
                "data": json.dumps(current_status)
            }

        await asyncio.sleep(0.5)


@app.get('/sse/videostream', tags=["Server Sent Event"], description="Server Sent Event to send video stream to client")
async def sse_video_stream(request: Request):
    return EventSourceResponse(video_generator(request))



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