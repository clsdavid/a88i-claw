from typing import TypedDict, Annotated, Sequence, Dict, Any
import operator
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from autocrab.core.agent.memory import HybridMemoryStore
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage
from autocrab.core.models.config import settings
from autocrab.core.tools.bash import BASH_TOOL_SPEC, execute_bash_tool
from autocrab.core.tools.fs import fs_tools
from autocrab.core.tools.browser import browser_tools
from autocrab.core.tools.mcp import McpToolRegistry
from autocrab.core.plugins.loader import get_registered_schemas, execute_skill
from autocrab.core.sandbox.manager import SandboxManager

class AgentState(TypedDict, total=False):
    """
    The state dictionary passed between nodes in the LangGraph.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    context: str
    instructions: Any
    tool_choice: Any

async def build_context(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Pulls the latest conversational context from Hybrid Memory.
    """
    store = HybridMemoryStore(state["session_id"])
    
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
    
    llm = ChatOpenAI(
        model=settings.llm.model_name,
        api_key=settings.llm.api_key or "sk-dummy",
        base_url=settings.llm.base_url
    )
    
    # Gather tools
    tools = [BASH_TOOL_SPEC.model_dump()]
    
    # Add native python tools
    from langchain_core.utils.function_calling import convert_to_openai_function
    for tool in fs_tools + browser_tools:
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
                if tool_name == "bash":
                    if not sandbox:
                        sandbox = SandboxManager(session_id=state["session_id"])
                        sandbox.start_sandbox()
                    result_str = execute_bash_tool(sandbox, tool_args)
                elif tool_name in ["fs_read", "fs_write", "fs_list", "browser_tool"]:
                    # Native python tools execution mapping
                    tool_map = {t.name: t for t in fs_tools + browser_tools}
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
                
            tool_messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))
            
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
