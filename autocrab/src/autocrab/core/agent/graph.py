from typing import TypedDict, Annotated, Sequence, Dict, Any
import operator
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from autocrab.core.agent.memory import HybridMemoryStore

class AgentState(TypedDict):
    """
    The state dictionary passed between nodes in the LangGraph.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    context: str

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
    # [STUB] This node will eventually securely call the LLM provider.
    # For Phase 2 validation, we simply append a dummy AI message.
    dummy_msg = AIMessage(content="[STUB] I am the Brain. I comprehended the context.")
    return {"messages": [dummy_msg]}

async def execute_tools(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Executes tool calls parsed from the LLM response in a Sandbox.
    """
    # [STUB] Phase 3 will fill this with Docker SDK sandboxing.
    return {"messages": []}

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
