from app import armmane
from app import sysmane
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
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


@app.get("/")
async def root():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "envoriment": {
                "current_path": sys.getCurrentPath(),
                "current_model": sys.getCurrentModel(),
                "models": sys.listModelFolder()
            }
        }
    )

@app.get("/model", tags=["Model"])
async def model():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Return list of models",
            "models": sys.listModelFolder()
        }
    )

@app.post("/model/{model_name}/set", tags=["Model"])
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
    sys.setCurrentModel(model_name)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Set current model to {}".format(model_name)
        }
    )


@app.get("/model/{model_name}/config", tags=["Model"])
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

# Run the server by typing this command in the terminal:
# uvicorn server:app --reload