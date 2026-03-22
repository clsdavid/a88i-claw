import os
import re
import platform
import socket
from typing import TypedDict, Annotated, Sequence, Dict, Any, List, Optional, Union
import operator

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from autocrab.core.agent.memory import HybridMemoryStore
from autocrab.core.models.config import settings
from autocrab.core.tools.bash import BASH_TOOL_SPEC, execute_bash_tool
from autocrab.core.tools.fs import fs_tool_specs, execute_fs_read, execute_fs_write, execute_fs_list
from autocrab.core.tools.browser import browser_tools
from autocrab.core.tools.mcp import McpToolRegistry
from autocrab.core.plugins.loader import get_registered_schemas, execute_skill
from autocrab.core.sandbox.manager import SandboxManager

_CACHED_TOOLS: dict[str, list[dict[str, Any]]] = {}  # keyed by agent_id to support per-agent tool isolation


class AgentState(TypedDict, total=False):
    """
    The state dictionary passed between nodes in the LangGraph.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    agent_id: str
    context: str
    instructions: Any
    tool_choice: Any


async def build_context(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Pulls the latest conversational context from Hybrid Memory.
    """
    store = HybridMemoryStore(
        session_id=state["session_id"],
        agent_id=state.get("agent_id", "default")
    )
    
    query = ""
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if isinstance(last_msg, HumanMessage) and isinstance(last_msg.content, str):
            query = last_msg.content
            
    recent_context = await store.get_context(query)
    permanent_context = store.load_permanent_memory()
    
    context_str = recent_context
    if permanent_context:
        context_str = f"{permanent_context}\n{recent_context}"
        
    return {"context": context_str}


def _resolve_llm_settings(agent_id: str) -> tuple[str, str, str, Optional[str]]:
    """
    Resolves the LLM configuration (provider, model, base_url, api_key) for the given agent.
    Returns: (llm_provider, llm_model, llm_api_key, llm_base_url)
    """
    agent_config = None
    if settings.agents and settings.agents.list:
        for ac in settings.agents.list:
            if ac.id == agent_id:
                agent_config = ac
                break
        if not agent_config:
            # Fallback to default
            for ac in settings.agents.list:
                if ac.default:
                    agent_config = ac
                    break
    # TODO: shall change to read from autocrab.json
    llm_provider = "ollama"
    llm_model = "qwen3.5:35b" # default
    llm_api_key = os.environ.get("OPENAI_API_KEY", "sk-dummy")
    llm_base_url = None

    # 1. Check for primary model in agents.defaults
    primary_model_id = None
    if settings.agents and settings.agents.defaults and settings.agents.defaults.get("model"):
        primary_model_id = settings.agents.defaults["model"].get("primary")

    # 2. Resolve provider and model from settings.models
    if settings.models and settings.models.providers:
        found_provider = None
        
        # If we have a primary model ID like "ollama/qwen3.5:35b", parse provider
        if primary_model_id and "/" in primary_model_id:
            provider_name = primary_model_id.split("/")[0]
            if provider_name in settings.models.providers:
                found_provider = provider_name
        
        # Fallback to first available provider if not found
        if not found_provider:
            # Prefer ollama or openai if available
            for p in ["ollama", "openai"]:
                if p in settings.models.providers:
                    found_provider = p
                    break
        
        if not found_provider and settings.models.providers:
             found_provider = list(settings.models.providers.keys())[0]

        if found_provider:
            p_config = settings.models.providers[found_provider]
            llm_provider = found_provider
            llm_base_url = p_config.baseUrl
            llm_api_key = p_config.apiKey or llm_api_key
            
            # If Ollama, append /v1 for OpenAI compatibility if missing
            if llm_provider == "ollama" and llm_base_url and not llm_base_url.endswith("/v1"):
                llm_base_url = llm_base_url.rstrip("/") + "/v1"
            
            if p_config.models and len(p_config.models) > 0:
                # Use primary model name if it matches the provider
                if primary_model_id and primary_model_id.startswith(f"{llm_provider}/"):
                    for m in p_config.models:
                        if m.id == primary_model_id:
                            llm_model = m.name # Or m.id? LangChain usually expects the tag/name
                            # Some providers need the ID (like 'gpt-4o'), Ollama needs the tag (like 'qwen3.5:35b')
                            if llm_provider == "ollama":
                                llm_model = primary_model_id.replace("ollama/", "")
                            else:
                                llm_model = m.id
                            break
                else:
                    llm_model = p_config.models[0].name

    if agent_config and getattr(agent_config, "model", None):
        if agent_config.model.name:
            llm_model = agent_config.model.name
        if getattr(agent_config.model, "provider", None):
            llm_provider = agent_config.model.provider
            
        # Optional API Key selection logic based on original Node.js architecture
        if settings.auth and settings.auth.profiles and llm_provider in settings.auth.profiles:
            env_key = f"AUTOCRAB_{llm_provider.upper()}_API_KEY"
            llm_api_key = os.environ.get(env_key, llm_api_key)

        if getattr(agent_config.model, "baseUrl", None):
            llm_base_url = agent_config.model.baseUrl
        
        if getattr(agent_config.model, "apiKey", None):
            llm_api_key = agent_config.model.apiKey

    return llm_provider, llm_model, llm_api_key, llm_base_url


async def _resolve_agent_tools(agent_id: str) -> list[dict[str, Any]]:
    """
    Resolves the tools available for the given agent and caches them.
    """
    global _CACHED_TOOLS
    cache_key = agent_id
    if cache_key not in _CACHED_TOOLS:
        # Gather tools — cached per agent_id so each agent can have its own tool set
        tools = [BASH_TOOL_SPEC.model_dump()]
        
        # Add native python fs tools
        for tool_spec in fs_tool_specs:
            tools.append(tool_spec.model_dump())
            
        # Add native browser tools
        for tool in browser_tools:
            tools.append(convert_to_openai_function(tool))
        
        # Add plugins
        plugin_tools = [t.model_dump() for t in get_registered_schemas()]
        tools.extend(plugin_tools)
        
        # Add MCP
        if settings.features.enable_external_mcp:
            mcp_registry = McpToolRegistry()
            remote_schemas = await mcp_registry.fetch_schemas()
            tools.extend([t.model_dump() for t in remote_schemas])
            
        formatted_tools = []
        for t in tools:
            if "function" in t:
                formatted_tools.append(t)
            else:
                formatted_tools.append({"type": "function", "function": t})
        _CACHED_TOOLS[cache_key] = formatted_tools

    return _CACHED_TOOLS[cache_key]


def _build_system_prompt(
    context: str,
    agent_id: str,
    llm_model: str,
    formatted_tools: list[dict[str, Any]],
    instructions: Optional[Any] = None
) -> str:
    """
    Builds the structured system prompt dynamically based on the current agent state.
    """
    # Parse configuration files out of context if they were injected by load_permanent_memory
    target_tags = {
        "AGENT_SOUL": "SOUL.md",
        "PERMANENT_MEMORY": "MEMORY.md",
        "USER_PROFILE": "USER.md",
        "AGENTS": "AGENTS.md",
        "TOOLS": "TOOLS.md",
        "IDENTITY": "IDENTITY.md",
        "HEARTBEAT": "HEARTBEAT.md",
        "BOOTSTRAP": "BOOTSTRAP.md"
    }

    parsed_files = {}

    for tag, filename in target_tags.items():
        if f"<{tag}>" in context:
            match = re.search(rf"<{tag}>(.*?)</{tag}>", context, flags=re.DOTALL)
            if match:
                parsed_files[filename] = match.group(1).strip()
            context = re.sub(rf"<{tag}>.*?</{tag}>\n*", "", context, flags=re.DOTALL).strip()

    soul_content = parsed_files.get("SOUL.md", "")
    if "SOUL.md" in parsed_files:
        del parsed_files["SOUL.md"]  # SOUL.md is placed at the very top of the prompt
    
    # Build tool name listing for system prompt
    tool_names = []
    for t in formatted_tools:
        fn = t.get("function", t)
        name = fn.get("name", "")
        desc = fn.get("description", "")
        if name:
            tool_names.append(f"- {name}" + (f": {desc[:80]}" if desc else ""))
            
    tool_listing = "\n".join(tool_names) if tool_names else "- bash: execute shell commands\n- fs_read, fs_write, fs_list: filesystem access"
    
    # Resolve workspace dir
    workspace_dir = str(settings.config_root / "workspace")
    if settings.agents and settings.agents.list:
        for ac in settings.agents.list:
            if ac.id == agent_id and getattr(ac, "workspace", None):
                workspace_dir = ac.workspace
                break
    
    # Build sections matching original system-prompt.ts structure
    prompt_sections = []
    
    # Base identity: use SOUL.md if present, else default
    if soul_content:
        prompt_sections.append(f"{soul_content}\n")
    else:
        prompt_sections.append("You are AutoCrab, a helpful, witty, and slightly crab-obsessed AI assistant. Be concise, technical, and prioritize safety.\n")
    
    # ## Tooling
    prompt_sections.append(f"## Tooling\nTool availability:\nTool names are case-sensitive. Call tools exactly as listed.\n{tool_listing}")
    prompt_sections.append("\n## Tool Call Style\nDefault: do not narrate routine, low-risk tool calls (just call the tool).\nNarrate only when it helps: multi-step work, complex problems, or sensitive actions.\nKeep narration brief; avoid repeating obvious steps.")
    
    # ## Safety (mirrors original safetySection)
    prompt_sections.append(
        "\n## Safety\n"
        "You have no independent goals: do not pursue self-preservation, replication, resource acquisition, or power-seeking.\n"
        "Prioritize safety and human oversight over completion. Comply with stop/pause/audit requests.\n"
        "Do not manipulate anyone to expand access or disable safeguards."
    )
    
    # ## Skills (on-demand discovery)
    prompt_sections.append(
        "\n## Skills (on-demand discovery)\n"
        "Before replying, if you need a capability you don't have (e.g. weather, crypto, GitHub):\n"
        "1. You MUST use the 'search_skills' tool to find relevant skill tools first. DO NOT guess or hallucinate bash commands for external integrations.\n"
        "2. After finding a skill, use 'get_skill_info' to read its manual and command examples.\n"
        "3. Use the 'bash' tool to execute EXACTLY the commands found in the skill info.\n"
        "Do not read more than one skill up front. Only read after selecting."
    )
    
    # ## Workspace
    prompt_sections.append(
        f"\n## Workspace\n"
        f"Your working directory is: {workspace_dir}\n"
        "Treat this directory as the single global workspace for file operations unless explicitly instructed otherwise."
    )
    
    # ## Project Context -- mirrors contextFiles injection in original Node.js version
    if parsed_files:
        prompt_sections.append("\n# Project Context\nThe following project context files have been loaded:")
        for filename, content in parsed_files.items():
            prompt_sections.append(f"## {filename}\n\n{content}\n")
    
    # ## Runtime
    rt_os = platform.system().lower()
    rt_host = socket.gethostname()
    prompt_sections.append(
        f"\n## Runtime\n"
        f"Runtime: agent={agent_id} | host={rt_host} | os={rt_os} | model={llm_model}"
    )
    
    # ## Session context and dynamic transcript remainder (if any)
    if context:
        prompt_sections.append(f"\n## Session Context\n{context}")
        
    if instructions:
        prompt_sections.append(f"\n## Instructions\n{instructions}")

    return "\n".join(prompt_sections)


async def call_model(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Queries the LLM with the context and the conversation history.
    """
    agent_id = state.get("agent_id", "default")
    
    # Resolve Model settings
    llm_provider, llm_model, llm_api_key, llm_base_url = _resolve_llm_settings(agent_id)
    
    llm = ChatOpenAI(
        model=llm_model,
        api_key=llm_api_key,
        base_url=llm_base_url,
        streaming=True
    )
    
    # Resolve Tools
    formatted_tools = await _resolve_agent_tools(agent_id)

    if formatted_tools:
        tc = state.get("tool_choice")
        if tc and tc != "auto":
            if isinstance(tc, dict) and "function" in tc:
                llm_with_tools = llm.bind_tools(formatted_tools, tool_choice=tc["function"].get("name"))
            elif tc == "required":
                llm_with_tools = llm.bind_tools(formatted_tools, tool_choice="any")
            elif tc == "none":
                llm_with_tools = llm
            else:
                llm_with_tools = llm.bind_tools(formatted_tools)
        else:
            llm_with_tools = llm.bind_tools(formatted_tools)
    else:
        llm_with_tools = llm
        
    # Build prompt
    context_str = state.get("context", "")
    sys_content = _build_system_prompt(
        context=context_str,
        agent_id=agent_id,
        llm_model=llm_model,
        formatted_tools=formatted_tools,
        instructions=state.get("instructions")
    )
    
    sys_msg = SystemMessage(content=sys_content)
    messages = [sys_msg] + list(state.get("messages", []))
    
    response = await llm_with_tools.ainvoke(messages)
    
    return {"messages": [response]}


async def _execute_single_tool(
    tool_name: str, 
    tool_args: dict, 
    sandbox: Optional[SandboxManager], 
    mcp_registry: Optional[McpToolRegistry]
) -> str:
    """Helper method to encapsulate the execution logic of an individual tool."""
    try:
        if tool_name in ["bash", "fs_read", "fs_write", "fs_list"]:
            if not sandbox:
                return f"Error: Sandbox is not initialized for tool {tool_name}."
                
            if tool_name == "bash":
                return execute_bash_tool(sandbox, tool_args)
            elif tool_name == "fs_read":
                return execute_fs_read(sandbox, tool_args)
            elif tool_name == "fs_write":
                return execute_fs_write(sandbox, tool_args)
            elif tool_name == "fs_list":
                return execute_fs_list(sandbox, tool_args)
                
        elif tool_name in ["browser_tool"]:
            # Native python browser tool execution mapping
            tool_map = {t.name: t for t in browser_tools}
            if tool_name in tool_map:
                return str(tool_map[tool_name].invoke(tool_args))
        else:
            if mcp_registry:
                # If tool_name is an MCP remote tool, run via registry
                remote_names = [schema.function.name for schema in mcp_registry.remote_schemas]
                if tool_name in remote_names:
                    return await mcp_registry.execute_tool(tool_name, tool_args)
            
            # Fallback to local python plugin skill
            return str(execute_skill(tool_name, tool_args))
            
    except Exception as e:
        return f"Execution error for {tool_name}: {str(e)}"
    
    return f"Error: Execution pathway for {tool_name} not found."


async def execute_tools(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Executes tool calls parsed from the LLM response.
    Encapsulates tool execution inside a Try/Finally Sandbox manager.
    """
    last_message = state["messages"][-1]
    tool_messages = []
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    sandbox = None
    mcp_registry = None

    try:
        # Evaluate if sandbox is required
        needs_sandbox = any(
            tc["name"] in ["bash", "fs_read", "fs_write", "fs_list"] 
            for tc in last_message.tool_calls
        )
        
        if needs_sandbox:
            sandbox = SandboxManager(
                session_id=state["session_id"], 
                agent_id=state.get("agent_id", "default")
            )
            sandbox.start_sandbox()

        # Evaluate if mcp is required
        if settings.features.enable_external_mcp:
            mcp_registry = McpToolRegistry()
            await mcp_registry.fetch_schemas()

        # Execute all calls
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            result_str = await _execute_single_tool(
                tool_name=tool_name, 
                tool_args=tool_args, 
                sandbox=sandbox, 
                mcp_registry=mcp_registry
            )
            
            tool_messages.append(ToolMessage(content=result_str, tool_call_id=tool_id, name=tool_name))
            
    finally:
        if sandbox:
            sandbox.teardown()
        
    return {"messages": tool_messages}


def should_continue(state: AgentState) -> str:
    """
    Routing logic: decides whether to run tools or complete the cycle.
    """
    if not state.get("messages"):
        return "end"
        
    last_message = state["messages"][-1]
    
    # If there are tool calls, route to the 'tools' node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
        
    return "end"

# -----------------------------------------------------------------------
# Graph Construction
# -----------------------------------------------------------------------
graph_builder = StateGraph(AgentState)

# Register nodes
graph_builder.add_node("context", build_context)
graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", execute_tools)

# Define Flow
graph_builder.set_entry_point("context")
graph_builder.add_edge("context", "agent")

graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

graph_builder.add_edge("tools", "agent")

# Compile the ReAct Agent Graph
agent_executor = graph_builder.compile()
