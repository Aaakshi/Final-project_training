from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

app = FastAPI(title="Classification Service")

class ClassificationResult(BaseModel):
    doc_type: str
    confidence: float

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8").lower()
    
    # Simple classification logic based on keywords
    if any(word in text for word in ["invoice", "bill", "payment", "amount", "$"]):
        doc_type = "invoice"
        confidence = 0.95
    elif any(word in text for word in ["contract", "agreement", "terms", "conditions"]):
        doc_type = "contract"
        confidence = 0.90
    else:
        doc_type = "document"
        confidence = 0.80
    
    logger.info(f"Classified document {file.filename} as {doc_type}")
    return ClassificationResult(doc_type=doc_type, confidence=confidence)

@app.get("/ping")
async def ping():
    return {"message": "pong from Classification Service"}