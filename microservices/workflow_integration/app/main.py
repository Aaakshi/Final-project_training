
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Workflow Integration Service")

class NotificationRequest(BaseModel):
    doc_id: str
    assignee: str
    message: str = None

@app.get("/ping")
async def ping():
    return {"message": "pong from Workflow Integration Service"}

@app.post("/notify")
async def send_notification(request: NotificationRequest):
    """Send notification about document status"""
    
    # Simulate notification sending
    print(f"📧 Notification sent to {request.assignee} for document {request.doc_id}")
    
    return {
        "doc_id": request.doc_id,
        "assignee": request.assignee,
        "status": "notification sent",
        "timestamp": "2024-01-15T10:30:00Z"
    }

@app.post("/workflow/trigger")
async def trigger_workflow(workflow_data: dict):
    """Trigger workflow based on document processing"""
    
    workflow_type = workflow_data.get('type', 'standard')
    doc_id = workflow_data.get('doc_id')
    
    # Simulate workflow execution
    workflow_steps = [
        "Document received",
        "Classification completed",
        "Routing assigned",
        "Notification sent"
    ]
    
    return {
        "workflow_id": f"wf_{doc_id}",
        "type": workflow_type,
        "steps": workflow_steps,
        "status": "in_progress"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)
