import pytest
from fastapi.testclient import TestClient
from microservices.classification.app.main import app

client = TestClient(app)

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong from Classification Service"}

@pytest.mark.asyncio
async def test_classify_document():
    with open("test.txt", "w") as f:
        f.write("This is an invoice")
    with open("test.txt", "rb") as f:
        response = client.post("/classify", files={"file": ("test.txt", f, "text/plain")})
    assert response.status_code == 200
    assert response.json()["doc_type"] == "invoice"
    assert response.json()["confidence"] == 0.95