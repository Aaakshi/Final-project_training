from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from libs.utils.logger import setup_logger
import spacy

app = FastAPI(title="Classification Service")
nlp = spacy.load("en_core_web_sm")
logger = setup_logger(__name__)

class ClassificationResult(BaseModel):
    doc_type: str
    confidence: float

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    content = await file.read()
    doc = nlp(content.decode("utf-8"))
    # Mock classification logic
    doc_type = "invoice" if "invoice" in content.decode("utf-8").lower() else "contract"
    confidence = 0.95
    logger.info(f"Classified document {file.filename} as {doc_type}")
    return ClassificationResult(doc_type=doc_type, confidence=confidence)

@app.get("/ping")
async def ping():
    return {"message": "pong from Classification Service"}