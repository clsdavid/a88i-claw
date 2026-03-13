import pytest
import shutil
import os
from pathlib import Path
from autocrab.core.agent.memory import HybridMemoryStore
from autocrab.core.models.config import settings

@pytest.fixture
def clean_session_dir():
    # Setup test directory
    test_dir = ".sessions_test"
    original_dir = settings.session_dir
    settings.session_dir = test_dir
    
    yield
    
    # Teardown
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    settings.session_dir = original_dir

@pytest.mark.asyncio
async def test_hybrid_memory_local_fallback(clean_session_dir):
    session_id = "test-session-mem-123"
    store = HybridMemoryStore(session_id)
    
    # Ensure RAG is disabled for this test (verifying backward compatibility)
    store.use_rag = False
    
    # Simulate an interaction
    await store.add_interaction("user", "Hello Brain, this is a test.")
    await store.add_interaction("assistant", "Acknowledged. I am the Brain.")
    
    # Load context
    context = await store.get_context()
    
    # Assert exact markdown formatting expected by old system
    assert "User" in context
    assert "Assistant" in context
    assert "Hello Brain, this is a test." in context
    assert "Acknowledged. I am the Brain." in context

    # Check flat file was actually created on disk
    expected_path = Path(settings.session_dir) / session_id / "transcript.md"
    assert expected_path.exists()
