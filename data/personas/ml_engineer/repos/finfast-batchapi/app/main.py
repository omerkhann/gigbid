import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
from app.tasks import predict_task

app = FastAPI(title="Model Serving API")

class PredictRequest(BaseModel):
    data: list

class PredictResponse(BaseModel):
    task_id: str
    status: str

class PredictResult(BaseModel):
    result: list

@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    task = predict_task.delay(request.data)
    return PredictResponse(task_id=task.id, status="queued")

@app.get("/predict/{task_id}", response_model=PredictResult)
async def get_result(task_id: str):
    res = AsyncResult(task_id)
    if res.state == "SUCCESS":
        return PredictResult(result=res.get())
    elif res.state in {"PENDING", "STARTED"}:
        raise HTTPException(status_code=202, detail="Processing")
    else:
        raise HTTPException(status_code=500, detail="Task failed")
