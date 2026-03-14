from fastapi.testclient import TestClient
from autocrab.core.gateway.main import app
from unittest.mock import patch, AsyncMock

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "version" in response.json()

def test_create_response(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from langchain_core.messages import AIMessage
    
    mock_agent_executor = MagicMock()
    mock_agent_executor.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content="Real response processed successfully!")]
    })
    
    monkeypatch.setattr("autocrab.core.gateway.main.agent_executor", mock_agent_executor)
    
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
    
    # Verify the output matches mock
    output = data["output"]
    assert len(output) == 1
    assert output[0]["role"] == "assistant"
    
    content = output[0]["content"][0]["text"]
    assert "Real response processed successfully!" in content
