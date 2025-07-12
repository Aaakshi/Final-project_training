from fastapi import FastAPI
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

app = FastAPI(title="Workflow Integration Service")

@app.get("/")
async def root():
    return {"message": "Workflow Integration Service is running", "service": "workflow_integration"}

class NotificationRequest(BaseModel):
    doc_id: str
    assignee: str

class NotificationResponse(BaseModel):
    status: str
    message: str

@app.post("/notify")
async def send_notification(request: NotificationRequest):
    # Simulate sending notification
    message = f"Document {request.doc_id} has been assigned to {request.assignee}"

    logger.info(f"Sent notification for document {request.doc_id}")
    return NotificationResponse(status="sent", message=message)

@app.get("/ping")
async def ping():
    return {"message": "pong from Workflow Integration Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)