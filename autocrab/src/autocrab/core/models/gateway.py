from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict, Union, Literal

class StateVersion(BaseModel):
    presence: int = 0
    health: int = 0

class PresenceEntry(BaseModel):
    host: Optional[str] = None
    ip: Optional[str] = None
    version: Optional[str] = None
    platform: Optional[str] = None
    deviceFamily: Optional[str] = None
    modelIdentifier: Optional[str] = None
    mode: Optional[str] = None
    lastInputSeconds: Optional[int] = None
    reason: Optional[str] = None
    tags: Optional[List[str]] = None
    text: Optional[str] = None
    ts: int
    deviceId: Optional[str] = None
    roles: Optional[List[str]] = None
    scopes: Optional[List[str]] = None
    instanceId: Optional[str] = None

class SessionDefaults(BaseModel):
    defaultAgentId: str
    mainKey: str
    mainSessionKey: str
    scope: Optional[str] = "global"

class AgentIdentity(BaseModel):
    name: Optional[str] = None
    theme: Optional[str] = None
    emoji: Optional[str] = None
    avatar: Optional[str] = None
    avatarUrl: Optional[str] = None

class AgentSummary(BaseModel):
    id: str
    name: Optional[str] = None
    identity: Optional[AgentIdentity] = None

class AgentsListResult(BaseModel):
    defaultId: str
    mainKey: str
    scope: str = "global"
    agents: List[AgentSummary]

class ModelChoice(BaseModel):
    id: str
    name: str
    provider: str
    contextWindow: Optional[int] = None
    reasoning: Optional[bool] = None

class ModelsListResult(BaseModel):
    models: List[ModelChoice]

class UpdateAvailable(BaseModel):
    currentVersion: str
    latestVersion: str
    channel: str

class Snapshot(BaseModel):
    presence: List[PresenceEntry] = []
    health: Any = None
    stateVersion: StateVersion
    uptimeMs: int
    configPath: Optional[str] = None
    stateDir: Optional[str] = None
    sessionDefaults: Optional[SessionDefaults] = None
    authMode: Optional[Literal["none", "token", "password", "trusted-proxy"]] = "none"
    updateAvailable: Optional[UpdateAvailable] = None

class ClientInfo(BaseModel):
    id: str
    displayName: Optional[str] = None
    version: str
    platform: str
    deviceFamily: Optional[str] = None
    modelIdentifier: Optional[str] = None
    mode: str
    instanceId: Optional[str] = None

class DeviceInfo(BaseModel):
    id: str
    publicKey: str
    signature: str
    signedAt: int
    nonce: str

class AuthParams(BaseModel):
    token: Optional[str] = None
    deviceToken: Optional[str] = None
    password: Optional[str] = None

class ConnectParams(BaseModel):
    minProtocol: int
    maxProtocol: int
    client: ClientInfo
    caps: List[str] = []
    commands: Optional[List[str]] = None
    permissions: Optional[Dict[str, bool]] = None
    pathEnv: Optional[str] = None
    role: Optional[str] = None
    scopes: Optional[List[str]] = None
    device: Optional[DeviceInfo] = None
    auth: Optional[AuthParams] = None
    locale: Optional[str] = None
    userAgent: Optional[str] = None

class HelloOk(BaseModel):
    type: Literal["hello-ok"] = "hello-ok"
    protocol: int
    server: Dict[str, str]
    features: Dict[str, List[str]]
    snapshot: Snapshot
    canvasHostUrl: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    policy: Dict[str, int]

class ErrorShape(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    retryable: Optional[bool] = None
    retryAfterMs: Optional[int] = None

class RequestFrame(BaseModel):
    type: Literal["req"] = "req"
    id: str
    method: str
    params: Optional[Any] = None

class ResponseFrame(BaseModel):
    type: Literal["res"] = "res"
    id: str
    ok: bool
    payload: Optional[Any] = None
    error: Optional[ErrorShape] = None

class EventFrame(BaseModel):
    type: Literal["event"] = "event"
    event: str
    payload: Optional[Any] = None
    seq: Optional[int] = None
    stateVersion: Optional[StateVersion] = None

GatewayFrame = Union[RequestFrame, ResponseFrame, EventFrame]
