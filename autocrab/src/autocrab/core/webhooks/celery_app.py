from celery import Celery
import os

# Default to a local redis instance for broker/backend, but allow environment overrides
REDIS_URL = os.getenv("AUTOCRAB_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "autocrab_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task
def process_incoming_webhook(provider: str, payload: dict):
    """
    Background task to securely process high-volume incoming webhooks 
    (Discord, Slack, etc.) without blocking the main FastAPI event loop.
    """
    from autocrab.core.agent.memory import HybridMemoryStore
    from autocrab.core.agent.graph import agent_executor
    from langchain_core.messages import HumanMessage
    import asyncio
    
    # Run the async agent loop in a new event loop for this worker thread
    async def _run_agent():
        # In a real system, you map the webhook payload to a session ID
        session_id = payload.get("channel_id", "default_webhook_session")
        content = payload.get("text", "")
        
        if not content:
            return "No content"
            
        initial_state = {
            "messages": [HumanMessage(content=content)],
            "session_id": session_id,
            "context": "" # Context builder node will fill this
        }
        
        # Execute the agent cycle
        final_state = await agent_executor.ainvoke(initial_state)
        
        last_msg = final_state["messages"][-1]
        
        # Save response back to memory
        store = HybridMemoryStore(session_id)
        await store.add_interaction("assistant", last_msg.content)
        
        # Note: A production system would then transmit `last_msg.content` 
        # back to the Discord/Slack API here.
        return last_msg.content

    return asyncio.run(_run_agent())
