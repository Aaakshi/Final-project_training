import pytest
from fastapi.testclient import TestClient
from microservices.workflow_integration.app.main import app

client = TestClient(app)

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong from Workflow Integration Service"}

@pytest.mark.asyncio
async def test_send_notification():
    response = client.post("/notify", json={"doc_id": "123e4567-e89b-12d3-a456-426614174000", "assignee": "finance_team"})
    assert response.status_code == 200
    assert response.json()["status"] == "notification sent"