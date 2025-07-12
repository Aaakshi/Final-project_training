import pytest
from fastapi.testclient import TestClient
from microservices.api_gateway.app.main import app as api_app
from microservices.classification.app.main import app as class_app
from microservices.routing_engine.app.main import app as route_app
from microservices.content_analysis.app.main import app as analysis_app
from microservices.workflow_integration.app.main import app as workflow_app

api_client = TestClient(api_app)
class_client = TestClient(class_app)
route_client = TestClient(route_app)
analysis_client = TestClient(analysis_app)
workflow_client = TestClient(workflow_app)

@pytest.mark.asyncio
async def test_full_document_flow():
    # Step 1: Classify document
    with open("test.txt", "w") as f:
        f.write("This is an invoice")
    with open("test.txt", "rb") as f:
        class_response = class_client.post("/classify", files={"file": ("test.txt", f, "text/plain")})
    assert class_response.status_code == 200
    doc_type = class_response.json()["doc_type"]
    
    # Step 2: Route document
    route_response = route_client.post("/route", json={"doc_id": "123e4567-e89b-12d3-a456-426614174000", "doc_type": doc_type})
    assert route_response.status_code == 200
    assignee = route_response.json()["assignee"]
    
    # Step 3: Analyze content
    analysis_response = analysis_client.post("/analyze", json={"doc_id": "123e4567-e89b-12d3-a456-426614174000", "content": "John Doe signed on 2025-07-11"})
    assert analysis_response.status_code == 200
    
    # Step 4: Send notification
    workflow_response = workflow_client.post("/notify", json={"doc_id": "123e4567-e89b-12d3-a456-426614174000", "assignee": assignee})
    assert workflow_response.status_code == 200