import pytest
import shutil
import os
from langchain_core.messages import HumanMessage
from autocrab.core.agent.graph import agent_executor
from autocrab.core.models.config import settings

@pytest.fixture
def clean_session_dir():
    test_dir = ".sessions_test_graph"
    original_dir = settings.session_dir
    settings.session_dir = test_dir
    yield
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    settings.session_dir = original_dir

@pytest.mark.asyncio
async def test_agent_graph_execution(clean_session_dir):
    """
    Tests that the LangGraph cycle correctly initializes, routes to the agent node,
    pulls context, and returns a dummy completion without crashing.
    """
    initial_state = {
        "messages": [HumanMessage(content="Test graph execution")],
        "session_id": "test-session-graph-1",
        "context": ""
    }
    
    # Invoke the graph
    final_state = await agent_executor.ainvoke(initial_state)
    
    # Should have the original human message + the dummy AI message
    assert len(final_state["messages"]) == 2
    
    last_message = final_state["messages"][-1]
    assert "I comprehended the context" in last_message.content
