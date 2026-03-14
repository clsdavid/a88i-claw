from typing import Optional, List, Dict, Union, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field

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

class LLMSettings(BaseModel):
    provider: Literal["openai", "ollama"] = "openai"
    model_name: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

class AutoCrabSettings(BaseSettings):
    """
    Core Configuration Settings for AutoCrab.
    Reads from environment variables or .env file.
    Prefix matching ensures that AUTOCRAB_GATEWAY_PORT maps to gateway.port, etc.
    """
    model_config = SettingsConfigDict(
        env_prefix="AUTOCRAB_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Core gateway configurations matching the TypeScript Zod Schema
    gateway: GatewaySettings = GatewaySettings()

    # External Features (RAG, MCP, Master Agent)
    features: ExternalFeaturesSettings = ExternalFeaturesSettings()
    
    # LLM settings
    llm: LLMSettings = LLMSettings()
    
    # Session storage
    session_dir: str = ".sessions"
    db_url: str = "sqlite:///autocrab.db"

# Global settings instance
settings = AutoCrabSettings()
