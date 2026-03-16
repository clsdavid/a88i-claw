import os
from typing import TypedDict, Annotated, Sequence, Dict, Any
import operator
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from autocrab.core.agent.memory import HybridMemoryStore
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage
from autocrab.core.models.config import settings
from autocrab.core.tools.bash import BASH_TOOL_SPEC, execute_bash_tool
from autocrab.core.tools.fs import fs_tool_specs, execute_fs_read, execute_fs_write, execute_fs_list
from autocrab.core.tools.browser import browser_tools
from autocrab.core.tools.mcp import McpToolRegistry
from autocrab.core.plugins.loader import get_registered_schemas, execute_skill
from autocrab.core.sandbox.manager import SandboxManager

_CACHED_TOOLS = None

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
    
    # In a full implementation, we extract the latest query text here 
    # to feed into the Hybrid RAG search.
    query = ""
    if state["messages"]:
        last_msg = state["messages"][-1]
        if isinstance(last_msg, HumanMessage):
            query = last_msg.content
            
    recent_context = await store.get_context(query)
    return {"context": recent_context}

async def call_model(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Queries the LLM with the context and the conversation history.
    """
    agent_id = state.get("agent_id", "default")
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

    llm_provider = "openai"
    llm_model = "gpt-4o" # default
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

    if agent_config and agent_config.model:
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
    
    # If using local Ollama, we don't want it to fail on missing key if 'sk-dummy' is present
    # but Ollama ignores it anyway.
    
    llm = ChatOpenAI(
        model=llm_model,
        api_key=llm_api_key,
        base_url=llm_base_url,
        streaming=True
    )
    
    global _CACHED_TOOLS
    if _CACHED_TOOLS is None:
        # Gather tools
        tools = [BASH_TOOL_SPEC.model_dump()]
        
        # Add native python fs tools
        for tool_spec in fs_tool_specs:
            tools.append(tool_spec.model_dump())
            
        # Add native browser tools
        from langchain_core.utils.function_calling import convert_to_openai_function
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
        _CACHED_TOOLS = formatted_tools

    formatted_tools = _CACHED_TOOLS

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
        
    sys_content = f"You are AutoCrab, an advanced AI agent.\\nContext:\\n{state.get('context', '')}"
    
    # Inform about dynamic skill discovery
    sys_content += "\n\nAvailable Capabilities:\n- If you need a capability you don't currently have (e.g. weather, crypto, system control, GitHub issues), use 'search_skills' to find relevant tools.\n- After finding a skill, use 'get_skill_info' to read its manual and command examples.\n- Finally, use the 'bash' tool to execute any required commands found in the skill info."
    
    if state.get("instructions"):
        sys_content += f"\\n\\nInstructions:\\n{state['instructions']}"
        
    sys_msg = SystemMessage(content=sys_content)
    
    messages = [sys_msg] + list(state["messages"])
    response = await llm_with_tools.ainvoke(messages)
    
    return {"messages": [response]}

async def execute_tools(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Executes tool calls parsed from the LLM response in a Sandbox.
    """
    
    last_message = state["messages"][-1]
    tool_messages = []
    
    sandbox = None
    mcp_registry = None
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            result_str = f"Error: Tool {tool_name} not found."
            
            try:
                if tool_name in ["bash", "fs_read", "fs_write", "fs_list"]:
                    if not sandbox:
                        sandbox = SandboxManager(
                            session_id=state["session_id"], 
                            agent_id=state.get("agent_id", "default")
                        )
                        sandbox.start_sandbox()
                        
                    if tool_name == "bash":
                        result_str = execute_bash_tool(sandbox, tool_args)
                    elif tool_name == "fs_read":
                        result_str = execute_fs_read(sandbox, tool_args)
                    elif tool_name == "fs_write":
                        result_str = execute_fs_write(sandbox, tool_args)
                    elif tool_name == "fs_list":
                        result_str = execute_fs_list(sandbox, tool_args)
                        
                elif tool_name in ["browser_tool"]:
                    # Native python browser tool execution mapping
                    tool_map = {t.name: t for t in browser_tools}
                    if tool_name in tool_map:
                        result_str = str(tool_map[tool_name].invoke(tool_args))
                else:
                    if not mcp_registry:
                        mcp_registry = McpToolRegistry()
                        await mcp_registry.fetch_schemas()
                    
                    remote_names = [schema.function.name for schema in mcp_registry.remote_schemas]
                    
                    if tool_name in remote_names:
                        result_str = await mcp_registry.execute_tool(tool_name, tool_args)
                    else:
                        result_str = str(execute_skill(tool_name, tool_args))
                        
            except Exception as e:
                result_str = f"Execution error for {tool_name}: {str(e)}"
                
            tool_messages.append(ToolMessage(content=result_str, tool_call_id=tool_id, name=tool_name))
            
    if sandbox:
        sandbox.teardown()
        
    return {"messages": tool_messages}

def should_continue(state: AgentState) -> str:
    """
    Routing logic: decides whether to run tools or complete the cycle.
    """
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
