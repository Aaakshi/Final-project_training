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

app = FastAPI(title="Routing Engine Service")

class RoutingRequest(BaseModel):
    doc_id: str
    doc_type: str

class RoutingResponse(BaseModel):
    assignee: str
    priority: str

@app.post("/route")
async def route_document(request: RoutingRequest):
    # Simple routing logic based on document type
    if request.doc_type == "invoice":
        assignee = "finance_team"
        priority = "high"
    elif request.doc_type == "contract":
        assignee = "legal_team"
        priority = "medium"
    else:
        assignee = "general_team"
        priority = "low"

    logger.info(f"Routed document {request.doc_id} to {assignee}")
    return RoutingResponse(assignee=assignee, priority=priority)

@app.get("/ping")
async def ping():
    return {"message": "pong from Routing Engine Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)