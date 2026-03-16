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
    defaults: Optional[Dict[str, Any]] = None
    list: Optional[List[AgentConfig]] = None

class AgentBindingMatch(BaseModel):
    channel: str
    accountId: Optional[str] = None
    peer: Optional[Dict[str, str]] = None
    guildId: Optional[str] = None
    teamId: Optional[str] = None
    roles: Optional[List[str]] = None

class AgentRouteBinding(BaseModel):
    type: Optional[Literal["route"]] = "route"
    agentId: str
    comment: Optional[str] = None
    match: AgentBindingMatch

class AgentAcpBinding(BaseModel):
    type: Literal["acp"]
    agentId: str
    comment: Optional[str] = None
    match: AgentBindingMatch
    acp: Optional[Dict[str, Any]] = None

AgentBinding = Union[AgentRouteBinding, AgentAcpBinding]

class SessionConfig(BaseModel):
    dmScope: Optional[Literal["main", "per-peer", "per-channel-peer", "per-account-channel-peer"]] = "main"
    identityLinks: Optional[Dict[str, List[str]]] = None

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

class DiscordGuildChannelConfig(BaseModel):
    allow: Optional[bool] = True
    requireMention: Optional[bool] = None
    enabled: Optional[bool] = True
    users: Optional[List[str]] = None
    roles: Optional[List[str]] = None

class DiscordGuildEntry(BaseModel):
    slug: Optional[str] = None
    requireMention: Optional[bool] = None
    channels: Optional[Dict[str, DiscordGuildChannelConfig]] = None

class DiscordAccountConfig(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = True
    token: Optional[Union[str, Dict[str, Any]]] = None
    allowBots: Optional[Union[bool, Literal["mentions"]]] = False
    groupPolicy: Optional[Literal["open", "disabled", "allowlist"]] = "allowlist"
    guilds: Optional[Dict[str, DiscordGuildEntry]] = None

class DiscordConfig(DiscordAccountConfig):
    accounts: Optional[Dict[str, DiscordAccountConfig]] = None
    defaultAccount: Optional[str] = None

class TelegramConfig(BaseModel):
    enabled: Optional[bool] = True
    token: Optional[str] = None
    # Add more Telegram specific fields as needed

class ChannelsConfig(BaseModel):
    discord: Optional[DiscordConfig] = None
    telegram: Optional[TelegramConfig] = None
    # Add other channels as needed

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
    Custom Pydantic Settings Source that reads from the Node.js legacy config directory 
    (defaulting to ~/.autocrab_v2) using JSON5 to seamlessly ingest the configuration 
    while allowing ENV overriding.
    """
    def __init__(self, settings_cls, config_root: Path):
        super().__init__(settings_cls)
        self.config_root = config_root
        self._config_data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        config_path = self.config_root / "autocrab.json"
        
        # Priority 1: Direct path from ENV
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

    # Bootstrapping
    home_dir: str = str(Path.home() / ".autocrab_v2")
    
    @property
    def config_root(self) -> Path:
        return Path(os.environ.get("AUTOCRAB_HOME", self.home_dir))

    gateway: GatewaySettings = GatewaySettings()
    features: ExternalFeaturesSettings = ExternalFeaturesSettings()
    
    # Original JSON schemas
    agents: Optional[AgentsConfig] = None
    auth: Optional[AuthConfig] = None
    models: Optional[ModelsConfig] = None
    channels: Optional[ChannelsConfig] = None
    bindings: Optional[List[AgentBinding]] = None
    session: Optional[SessionConfig] = SessionConfig()

    # Fallback / Local Storage
    session_dir: Optional[str] = None
    db_url: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.session_dir:
            self.session_dir = str(self.config_root / "sessions")
        if not self.db_url:
            self.db_url = f"sqlite:///{self.config_root}/autocrab.db"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        home_dir = Path.home() / ".autocrab_v2"
        config_root = Path(os.environ.get("AUTOCRAB_HOME", str(home_dir)))
        
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            AutoCrabJsonSource(settings_cls, config_root),
            file_secret_settings,
        )

# Global settings instance
settings = AutoCrabSettings()
