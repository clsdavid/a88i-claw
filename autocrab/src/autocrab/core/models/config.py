import os
import json5
from pathlib import Path
from typing import Optional, List, Dict, Union, Literal, Any, Tuple
from pydantic import BaseModel, ConfigDict
from pydantic_settings import (
    BaseSettings, 
    SettingsConfigDict, 
    PydanticBaseSettingsSource,
)

class AgentModelConfig(BaseModel):
    provider: Optional[str] = None
    name: Optional[str] = None
    apiKey: Optional[str] = None
    baseUrl: Optional[str] = None

class AgentSandboxConfig(BaseModel):
    enabled: Optional[bool] = None
    image: Optional[str] = None
    workspaceAccess: Optional[Literal["rw", "ro", "none"]] = None

class AgentConfig(BaseModel):
    id: str
    default: Optional[bool] = False
    name: Optional[str] = None
    workspace: Optional[str] = None
    agentDir: Optional[str] = None
    model: Optional[AgentModelConfig] = None
    skills: Optional[List[str]] = None
    sandbox: Optional[AgentSandboxConfig] = None
    params: Optional[Dict[str, Any]] = None

class AgentsConfig(BaseModel):
    list: Optional[List[AgentConfig]] = None

class AuthProfileConfig(BaseModel):
    provider: str
    mode: Literal["api_key", "oauth", "token"]
    email: Optional[str] = None

class AuthConfig(BaseModel):
    profiles: Optional[Dict[str, AuthProfileConfig]] = None

class ModelDefinitionConfig(BaseModel):
    id: str
    name: str
    reasoning: Optional[bool] = False
    contextWindow: Optional[int] = None
    maxTokens: Optional[int] = None

class ModelProviderConfig(BaseModel):
    baseUrl: str
    apiKey: Optional[str] = None
    models: Optional[List[ModelDefinitionConfig]] = None

class ModelsConfig(BaseModel):
    mode: Optional[str] = None
    providers: Optional[Dict[str, ModelProviderConfig]] = None

class GatewaySettings(BaseModel):
    port: int = 5174
    mode: Literal["local", "remote"] = "local"
    bind: Literal["auto", "lan", "loopback", "custom", "tailnet"] = "auto"
    customBindHost: Optional[str] = None

class ExternalFeaturesSettings(BaseModel):
    enable_external_rag: bool = False
    rag_system_url: Optional[str] = None
    enable_external_mcp: bool = False
    mcp_provider_url: Optional[str] = None
    master_agent_url: Optional[str] = None

class AutoCrabJsonSource(PydanticBaseSettingsSource):
    """
    Custom Pydantic Settings Source that reads from the Node.js legacy ~./autocrab/autocrab.json
    using JSON5 to seamlessly ingest the configuration while allowing ENV overriding.
    """
    def __init__(self, settings_cls):
        super().__init__(settings_cls)
        self._config_data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        config_path = Path.home() / ".autocrab" / "autocrab.json"
        if env_path := os.environ.get("AUTOCRAB_CONFIG_PATH"):
            config_path = Path(env_path)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json5.load(f)
            except Exception as e:
                print(f"Warning: Failed to parse {config_path}: {e}")
        return {}

    def get_field_value(self, field, field_name: str) -> Tuple[Any, str, bool]:
        return self._config_data.get(field_name), field_name, False

    def __call__(self) -> Dict[str, Any]:
        return self._config_data

class AutoCrabSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTOCRAB_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    gateway: GatewaySettings = GatewaySettings()
    features: ExternalFeaturesSettings = ExternalFeaturesSettings()
    
    # Original JSON schemas
    agents: Optional[AgentsConfig] = None
    auth: Optional[AuthConfig] = None
    models: Optional[ModelsConfig] = None

    # Fallback / Local Storage
    session_dir: str = ".sessions"
    db_url: str = "sqlite:///autocrab.db"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            AutoCrabJsonSource(settings_cls),
            file_secret_settings,
        )

# Global settings instance
settings = AutoCrabSettings()
