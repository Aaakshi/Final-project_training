
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Routing Engine Service")

@app.get("/ping")
async def ping():
    return {"message": "pong from Routing Engine Service"}

@app.post("/route")
async def route_document(doc_data: dict):
    """Route document to appropriate department"""
    department = doc_data.get('department', 'general')
    priority = doc_data.get('priority', 'medium')
    
    # Simple routing logic
    routing_rules = {
        'finance': {'assignee': 'finance_team', 'priority_boost': 1},
        'legal': {'assignee': 'legal_team', 'priority_boost': 2},
        'hr': {'assignee': 'hr_team', 'priority_boost': 1},
        'it': {'assignee': 'it_team', 'priority_boost': 1},
        'general': {'assignee': 'general_team', 'priority_boost': 0}
    }
    
    rule = routing_rules.get(department, routing_rules['general'])
    
    return {
        "assignee": rule['assignee'],
        "department": department,
        "priority": priority,
        "routing_status": "routed"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
