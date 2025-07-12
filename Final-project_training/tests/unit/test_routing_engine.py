import pytest
from fastapi.testclient import TestClient
from microservices.routing_engine.app.main import app

client = TestClient(app)

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong from Routing Engine"}

@pytest.mark.asyncio
async def test_route_document():
    response = client.post("/route", json={"doc_id": "123e4567-e89b-12d3-a456-426614174000", "doc_type": "invoice"})
    assert response.status_code == 200
    assert response.json()["assignee"] == "finance_team"
    assert response.json()["priority"] == 1