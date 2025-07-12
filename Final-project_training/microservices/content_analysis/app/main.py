from fastapi import FastAPI
from pydantic import BaseModel
import sys
import os
import re

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

app = FastAPI(title="Content Analysis Service")

class AnalysisRequest(BaseModel):
    doc_id: str
    content: str

class AnalysisResponse(BaseModel):
    entities: dict

@app.post("/analyze")
async def analyze_content(request: AnalysisRequest):
    content = request.content
    
    # Extract entities using regex patterns
    entities = {
        "names": re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', content),
        "dates": re.findall(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}', content),
        "amounts": re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?', content),
        "emails": re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
    }
    
    # Filter empty lists
    entities = {k: v for k, v in entities.items() if v}
    
    logger.info(f"Analyzed document {request.doc_id}")
    return AnalysisResponse(entities=entities)

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}