from app import armmane
from app import sysmane
from app import serimane
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from loguru import logger
import json
# SSE
import asyncio
from sse_starlette.sse import EventSourceResponse

import sys



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
amn = armmane.ArmMane(sys)
seri = serimane.SeriMane(sys)

last_status = {}

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
    seri.setServo(servo, angle)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set servo {} to {}".format(servo, angle)
        }
    )
    

@app.get("/command/conv/{conv}/{mode}/{speed}", tags=["Command Deprecated"], description="Set conveyor to desired mode")
@app.post("/command/conv/{conv}/{mode}/{speed}", tags=["Command"], description="Set conveyor to desired mode")
async def command_conv(conv: int, mode: int = 0, speed: int = 255):
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
            "message": "Set conv {} to {}".format(conv, mode)
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
    
@app.get("/command/px/{instruction}", tags=["Command Deprecated"], description="Set multi-instruction (ElonX-instruction) to control the arm")
@app.post("/command/px/{instruction}", tags=["Command"], description="Set multi-instruction (ElonX-instruction) to control the arm")
async def command_px(instruction: str):
    seri.sendMessageToArduino("PX" + instruction + ">END")
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set instruction {}".format(instruction)
        }
    )

@app.get("/command/pi/{instruction}", tags=["Command Deprecated"], description="Set single-instruction (Elon-instruction) to control the arm")
@app.post("/command/pi/{instruction}", tags=["Command"], description="Set single-instruction (Elon-instruction) to control the arm")
async def command_pi(instruction: str):
    seri.sendMessageToArduino("PI" + instruction)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set instruction {}".format(instruction)
        }
    )
    

@app.get("/command/reset", tags=["Command Deprecated"], description="Reset arm to default waiting position")
@app.post("/command/reset", tags=["Command"], description="Reset arm to default waiting position")
async def command_reset():
    seri.resetServo()
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Reset arm"
        }
    )

async def event_generator(request: Request):
    last_status = None
    while True:
        current_status = seri.getCurrentStatus()
        # If client closes connection, stop sending events
        if await request.is_disconnected():
            break
        # If client reconnects or status changes, send current_status to client
        # if current_status != last_status:
        yield {
            "event": "arm_status",
            "data": json.dumps(current_status)
        }
        last_status = current_status
        await asyncio.sleep(0.1)
        

@app.get('/sse/status', tags=["Server Sent Event"], description="Server Sent Event to send arm status to client")
async def sse_status_stream(request: Request):
    return EventSourceResponse(event_generator(request))
    
    
    
        
        
        
    
    




# Run the server by typing this command in the terminal:
# uvicorn server:app --reload