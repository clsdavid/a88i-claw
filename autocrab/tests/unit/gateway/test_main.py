from fastapi.testclient import TestClient
from autocrab.core.gateway.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "version" in response.json()

def test_create_response_stub():
    payload = {
        "model": "stub-model",
        "input": "test prompt"
    }
    response = client.post("/v1/responses", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["object"] == "response"
    assert data["model"] == "stub-model"
    assert data["status"] == "completed"
    
    # Verify the stub output echoes the input
    output = data["output"]
    assert len(output) == 1
    assert output[0]["role"] == "assistant"
    
    content = output[0]["content"][0]["text"]
    assert "test prompt" in content
    assert "Brain not connected" in content
