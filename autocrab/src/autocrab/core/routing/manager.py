import re
from typing import Optional, List, Dict, Any, Union, Literal, Set
from pydantic import BaseModel
from autocrab.core.models.config import settings, AgentBinding, AgentRouteBinding, AgentBindingMatch

DEFAULT_ACCOUNT_ID = "default"
DEFAULT_AGENT_ID = "main"

VALID_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$", re.I)
INVALID_CHARS_RE = re.compile(r"[^a-z0-9_-]+")

def normalize_account_id(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_ACCOUNT_ID
    trimmed = value.strip().lower()
    if VALID_ID_RE.match(trimmed):
        return trimmed
    normalized = INVALID_CHARS_RE.sub("-", trimmed).strip("-")[:64]
    return normalized if normalized else DEFAULT_ACCOUNT_ID

def normalize_agent_id(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_AGENT_ID
    trimmed = value.strip().lower()
    if VALID_ID_RE.match(trimmed):
        return trimmed
    normalized = INVALID_CHARS_RE.sub("-", trimmed).strip("-")[:64]
    return normalized if normalized else DEFAULT_AGENT_ID

def build_agent_session_key(
    agent_id: str,
    channel: str,
    account_id: Optional[str] = None,
    peer: Optional[Dict[str, str]] = None,
    dm_scope: str = "main",
    identity_links: Optional[Dict[str, List[str]]] = None
) -> str:
    agent_id = normalize_agent_id(agent_id)
    channel = channel.strip().lower() or "unknown"
    
    peer_kind = peer.get("kind", "direct") if peer else "direct"
    peer_id = peer.get("id", "").strip().lower() if peer else ""

    if peer_kind == "direct":
        if dm_scope == "main":
            return f"agent:{agent_id}:main"
        
        # Identity links resolution would go here (simplified for now)
        if dm_scope == "per-account-channel-peer":
            acc_id = normalize_account_id(account_id)
            return f"agent:{agent_id}:{channel}:{acc_id}:direct:{peer_id}"
        if dm_scope == "per-channel-peer":
            return f"agent:{agent_id}:{channel}:direct:{peer_id}"
        if dm_scope == "per-peer":
            return f"agent:{agent_id}:direct:{peer_id}"
        return f"agent:{agent_id}:main"
    
    return f"agent:{agent_id}:{channel}:{peer_kind}:{peer_id or 'unknown'}"

class ResolvedRoute(BaseModel):
    agent_id: str
    channel: str
    account_id: str
    session_key: str
    matched_by: str

def resolve_agent_route(
    channel: str,
    account_id: Optional[str] = None,
    peer: Optional[Dict[str, str]] = None,
    guild_id: Optional[str] = None,
    team_id: Optional[str] = None,
    member_role_ids: Optional[List[str]] = None
) -> ResolvedRoute:
    channel = channel.strip().lower()
    account_id = normalize_account_id(account_id)
    peer_kind = peer.get("kind", "").lower() if peer else ""
    peer_id = peer.get("id", "").strip() if peer else ""
    member_role_set = set(member_role_ids or [])
    
    bindings = settings.bindings or []
    dm_scope = settings.session.dmScope if settings.session else "main"
    identity_links = settings.session.identityLinks if settings.session else None

    def choose(agent_id: str, matched_by: str) -> ResolvedRoute:
        session_key = build_agent_session_key(
            agent_id=agent_id,
            channel=channel,
            account_id=account_id,
            peer=peer,
            dm_scope=dm_scope,
            identity_links=identity_links
        )
        return ResolvedRoute(
            agent_id=agent_id,
            channel=channel,
            account_id=account_id,
            session_key=session_key,
            matched_by=matched_by
        )

    # 1. Exact Peer Match
    if peer_id:
        for b in bindings:
            m = b.match
            if m.channel == channel and m.peer and m.peer.get("id") == peer_id:
                 return choose(b.agentId, "binding.peer")

    # 2. Guild + Roles Match
    if guild_id and member_role_set:
        for b in bindings:
            m = b.match
            if m.channel == channel and m.guildId == guild_id and m.roles:
                if any(r in member_role_set for r in m.roles):
                    return choose(b.agentId, "binding.guild+roles")

    # 3. Guild Match
    if guild_id:
        for b in bindings:
            m = b.match
            if m.channel == channel and m.guildId == guild_id and not m.roles:
                return choose(b.agentId, "binding.guild")

    # 4. Team Match
    if team_id:
        for b in bindings:
            m = b.match
            if m.channel == channel and m.teamId == team_id:
                return choose(b.agentId, "binding.team")

    # 5. Account Match
    for b in bindings:
        m = b.match
        if m.channel == channel and m.accountId == account_id and m.accountId != "*":
            return choose(b.agentId, "binding.account")

    # 6. Channel Match (Wildcard account)
    for b in bindings:
        m = b.match
        if m.channel == channel and (not m.accountId or m.accountId == "*"):
             return choose(b.agentId, "binding.channel")

    # 7. Default Agent
    default_agent_id = DEFAULT_AGENT_ID
    if settings.agents and settings.agents.list:
        for agent in settings.agents.list:
            if agent.default:
                default_agent_id = agent.id
                break
    
    return choose(default_agent_id, "default")
