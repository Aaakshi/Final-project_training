from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import sys
import os
import uvicorn

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

@app.get("/")
async def root():
    return {"message": "Classification Service is running", "service": "classification"}

class ClassificationResponse(BaseModel):
    doc_type: str
    department: str
    confidence: float
    priority: str
    extracted_text: str
    page_count: int
    language: str
    tags: list

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    # Read file content
    content = await file.read()
    text_content = content.decode('utf-8', errors='ignore') if content else ""

    # Simple classification logic
    content_lower = text_content.lower()

    if "invoice" in content_lower or "payment" in content_lower or "finance" in content_lower:
        doc_type = "invoice"
        department = "finance"
        confidence = 0.9
        priority = "high"
        tags = ["finance", "invoice"]
    elif "contract" in content_lower or "agreement" in content_lower or "legal" in content_lower:
        doc_type = "contract"
        department = "legal"
        confidence = 0.85
        priority = "medium"
        tags = ["legal", "contract"]
    elif "employee" in content_lower or "hr" in content_lower:
        doc_type = "hr_document"
        department = "hr"
        confidence = 0.8
        priority = "medium"
        tags = ["hr", "employee"]
    elif "it" in content_lower or "technology" in content_lower:
        doc_type = "it_document"
        department = "it"
        confidence = 0.75
        priority = "low"
        tags = ["it", "technology"]
    else:
        doc_type = "general"
        department = "general"
        confidence = 0.6
        priority = "low"
        tags = ["general"]

    logger.info(f"Classified document {file.filename} as {doc_type}")

    return ClassificationResponse(
        doc_type=doc_type,
        department=department,
        confidence=confidence,
        priority=priority,
        extracted_text=text_content[:500],  # First 500 chars
        page_count=1,
        language="en",
        tags=tags
    )

@app.get("/ping")
async def ping():
    return {"message": "pong from Classification Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)