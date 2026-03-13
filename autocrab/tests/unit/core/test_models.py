from autocrab.core.models.api import CreateResponseBody, ResponseResource
from autocrab.core.models.config import AutoCrabSettings

def test_config_defaults():
    settings = AutoCrabSettings()
    assert settings.gateway.port == 5174
    assert settings.gateway.mode == "local"
    assert settings.features.enable_external_rag is False
    assert settings.features.enable_external_mcp is False

def test_api_models_basic():
    body = {
        "model": "gpt-4",
        "input": "hello world",
    }
    request = CreateResponseBody(**body)
    assert request.model == "gpt-4"
    assert request.input == "hello world"

def test_api_models_complex():
    body = {
        "model": "claude-3",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": "Analyze this."
            }
        ]
    }
    request = CreateResponseBody(**body)
    item = request.input[0]
    assert item.type == "message"
    assert item.role == "user"
    assert item.content == "Analyze this."
