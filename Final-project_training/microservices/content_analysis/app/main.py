from fastapi import FastAPI
from pydantic import BaseModel
from libs.utils.logger import setup_logger
import pandas as pd

app = FastAPI(title="Content Analysis Service")
logger = setup_logger(__name__)

class AnalysisRequest(BaseModel):
    doc_id: str
    content: str

class AnalysisResponse(BaseModel):
    entities: dict

@app.post("/analyze")
async def analyze_content(request: AnalysisRequest):
    # Mock entity extraction
    entities = {"names": ["John Doe"], "dates": ["2025-07-11"], "amounts": ["$1000"]}
    logger.info(f"Analyzed document {request.doc_id}")
    return AnalysisResponse(entities=entities)

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}