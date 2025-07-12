from fastapi import FastAPI
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

app = FastAPI(title="Routing Engine Service")

class RoutingRequest(BaseModel):
    doc_id: str
    doc_type: str

class RoutingResponse(BaseModel):
    assignee: str
    priority: int

@app.post("/route")
async def route_document(request: RoutingRequest):
    # Mock routing logic
    assignee = "finance_team" if request.doc_type == "invoice" else "legal_team"
    priority = 1
    logger.info(f"Routed document {request.doc_id} to {assignee}")
    return RoutingResponse(assignee=assignee, priority=priority)

@app.get("/ping")
async def ping():
    return {"message": "pong from Routing Engine Service"}

class RoutingResponse(BaseModel):
    assignee: str
    department: str

@app.post("/route")
async def route_document(request: RoutingRequest):
    # Mock routing logic based on document type
    if request.doc_type == "invoice":
        assignee = "finance_team"
        department = "Finance"
    elif request.doc_type == "contract":
        assignee = "legal_team"
        department = "Legal"
    else:
        assignee = "general_team"
        department = "General"
    
    logger.info(f"Routed document {request.doc_id} to {assignee}")
    return RoutingResponse(assignee=assignee, department=department)

@app.get("/ping")
async def ping():
    return {"message": "pong from Routing Engine Service"}
