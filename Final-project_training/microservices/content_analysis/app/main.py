from fastapi import FastAPI
from pydantic import BaseModel
import sys
import os
import uvicorn
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

@app.post("/analyze")
async def analyze_content(request: AnalysisRequest):
    # Simple content analysis
    entities = {
        "names": [],
        "dates": [],
        "amounts": []
    }

    # Basic entity extraction
    # Extract dates
    date_pattern = r'\d{4}-\d{2}-\d{2}'
    entities["dates"] = re.findall(date_pattern, request.content)

    # Extract potential names (capitalized words)
    name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
    entities["names"] = re.findall(name_pattern, request.content)

    # Extract amounts
    amount_pattern = r'\$\d+\.?\d*'
    entities["amounts"] = re.findall(amount_pattern, request.content)

    logger.info(f"Analyzed content for document {request.doc_id}")
    return {"entities": entities, "sentiment": "neutral"}

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)