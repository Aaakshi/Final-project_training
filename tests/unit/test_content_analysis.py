import pytest
from fastapi.testclient import TestClient
from microservices.content_analysis.app.main import app

client = TestClient(app)

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong from Content Analysis Service"}

@pytest.mark.asyncio
async def test_analyze_content():
    response = client.post("/analyze", json={"doc_id": "123e4567-e89b-12d3-a456-426614174000", "content": "John Doe signed on 2025-07-11"})
    assert response.status_code == 200
    assert response.json()["entities"]["names"] == ["John Doe"]
    assert response.json()["entities"]["dates"] == ["2025-07-11"]