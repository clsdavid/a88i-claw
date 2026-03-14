import pytest
import shutil
import os
from unittest.mock import patch, AsyncMock
from langchain_core.messages import AIMessage
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
async def test_agent_graph_execution(monkeypatch, clean_session_dir):
    """
    Tests that the LangGraph cycle correctly initializes, routes to the agent node,
    pulls context, and returns a mocked completion without crashing.
    """
    from langchain_core.messages import AIMessage, HumanMessage
    from autocrab.core.agent.graph import agent_executor
    
    class FakeChatOpenAI:
        def __init__(self, *args, **kwargs):
            pass
            
        def bind_tools(self, tools, *args, **kwargs):
            return self
            
        async def ainvoke(self, messages, *args, **kwargs):
            return AIMessage(content="I comprehended the context")

    monkeypatch.setattr("autocrab.core.agent.graph.ChatOpenAI", FakeChatOpenAI)

    initial_state = {
        "messages": [HumanMessage(content="Test graph execution")],
        "session_id": "test-session-graph-1",
        "context": ""
    }
    
    # Invoke the graph
    final_state = await agent_executor.ainvoke(initial_state)
    
    # Should have the original human message + the mocked AI message
    assert len(final_state["messages"]) == 2
    
    last_message = final_state["messages"][-1]
    assert "I comprehended the context" in last_message.content
