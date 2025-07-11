from fastapi import FastAPI
from pydantic import BaseModel
from libs.utils.logger import setup_logger

app = FastAPI(title="Routing Engine")
logger = setup_logger(__name__)

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
    return {"message": "pong from Routing Engine"}