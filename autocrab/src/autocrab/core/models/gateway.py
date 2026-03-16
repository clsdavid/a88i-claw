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

class ConfigIssue(BaseModel):
    path: str
    message: str

class ConfigFileSnapshot(BaseModel):
    path: str
    exists: bool
    valid: bool
    raw: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None
    resolved: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    hash: Optional[str] = None
    issues: List[ConfigIssue] = []
    warnings: List[ConfigIssue] = []
    legacyIssues: List[Any] = []

class SessionEntry(BaseModel):
    key: str # UI expects .key
    sessionId: str
    updatedAt: int
    systemSent: bool = False
    abortedLastRun: bool = False
    label: Optional[str] = None
    model: Optional[str] = None
    modelProvider: Optional[str] = None
    inputTokens: int = 0
    outputTokens: int = 0
    totalTokens: int = 0
    totalTokensFresh: bool = False

class SessionsListResult(BaseModel):
    sessions: List[SessionEntry]

class SkillRequirement(BaseModel):
    bins: List[str] = []
    anyBins: List[str] = []
    env: List[str] = []
    config: List[str] = []
    os: List[str] = []

class SkillStatusEntry(BaseModel):
    name: str
    description: str
    source: str
    bundled: bool
    filePath: str
    baseDir: str
    skillKey: str
    primaryEnv: Optional[str] = None
    emoji: Optional[str] = None
    homepage: Optional[str] = None
    always: bool = False
    disabled: bool = False
    blockedByAllowlist: bool = False
    eligible: bool = True
    requirements: SkillRequirement = Field(default_factory=SkillRequirement)
    missing: SkillRequirement = Field(default_factory=SkillRequirement)
    configChecks: List[Any] = []
    install: List[Any] = []

class SkillStatusReport(BaseModel):
    workspaceDir: str
    managedSkillsDir: str
    skills: List[SkillStatusEntry]

class UpdateAvailable(BaseModel):
    currentVersion: str
    latestVersion: str
    channel: str

class ExecApprovalsDefaults(BaseModel):
    security: Optional[str] = None
    ask: Optional[str] = None
    askFallback: Optional[str] = None
    autoAllowSkills: Optional[bool] = None

class ExecApprovalsAllowlistEntry(BaseModel):
    id: Optional[str] = None
    pattern: str
    lastUsedAt: Optional[int] = None
    lastUsedCommand: Optional[str] = None
    lastResolvedPath: Optional[str] = None

class ExecApprovalsAgent(ExecApprovalsDefaults):
    allowlist: Optional[List[ExecApprovalsAllowlistEntry]] = None

class ExecApprovalsFile(BaseModel):
    version: Optional[int] = 1
    socket: Optional[Dict[str, Any]] = None
    defaults: Optional[ExecApprovalsDefaults] = None
    agents: Optional[Dict[str, ExecApprovalsAgent]] = None

class ExecApprovalsSnapshot(BaseModel):
    path: str
    exists: bool
    hash: str
    file: ExecApprovalsFile

class AgentFileEntry(BaseModel):
    name: str
    path: str
    missing: bool
    size: Optional[int] = None
    updatedAtMs: Optional[int] = None
    content: Optional[str] = None

class AgentsFilesListResult(BaseModel):
    agentId: str
    workspace: str
    files: List[AgentFileEntry]

class AgentsFilesGetResult(BaseModel):
    agentId: str
    workspace: str
    file: AgentFileEntry

class AgentsFilesSetResult(BaseModel):
    ok: bool = True
    agentId: str
    workspace: str
    file: AgentFileEntry

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
    caps: Optional[List[str]] = []
    commands: Optional[List[str]] = None
    permissions: Optional[Dict[str, bool]] = None
    pathEnv: Optional[str] = None
    role: Optional[str] = None
    scopes: Optional[List[str]] = None
    device: Optional[DeviceInfo] = None
    auth: Optional[AuthParams] = None
    locale: Optional[str] = None
    userAgent: Optional[str] = None

class HelloOkPolicy(BaseModel):
    maxPayload: int = 10 * 1024 * 1024
    maxBufferedBytes: int = 100 * 1024 * 1024
    tickIntervalMs: int = 5000

class HelloOkFeatures(BaseModel):
    methods: List[str] = []
    events: List[str] = []

class HelloOkServer(BaseModel):
    version: str
    connId: str

class HelloOk(BaseModel):
    type: Literal["hello-ok"] = "hello-ok"
    protocol: int
    server: HelloOkServer
    features: HelloOkFeatures
    snapshot: Snapshot
    canvasHostUrl: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    policy: HelloOkPolicy

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
