from autocrab.core.plugins.base import ChannelEvent
from autocrab.core.routing.manager import resolve_agent_route, build_agent_session_key
from autocrab.core.agent.graph import agent_executor
from langchain_core.messages import HumanMessage
from autocrab.core.models.config import settings
from autocrab.core.plugins.loader import get_channel_plugin

async def handle_channel_event(event: ChannelEvent):
    """
    Main entry point for events coming from channel plugins.
    Resolves the route, executes the agent, and sends back the reply.
    """
    # 1. Resolve agent routing
    route = resolve_agent_route(
        channel=event.channel,
        account_id=event.account_id,
        guild_id=event.guild_id,
        team_id=event.team_id,
        member_role_ids=event.member_role_ids or [],
        peer=event.peer
    )
    
    # 2. Build session key (important for HybridMemory persistence)
    dm_scope = "main"
    if event.peer["kind"] == "direct":
        dm_scope = getattr(settings.session, "dmScope", "main")
        
    session_key = build_agent_session_key(
        agent_id=route.agent_id,
        channel=event.channel,
        account_id=event.account_id,
        peer=event.peer,
        dm_scope=dm_scope
    )
    
    # 3. Invoke the LangGraph Brain
    initial_state = {
        "messages": [HumanMessage(content=event.text)],
        "session_id": session_key,
        "agent_id": route.agent_id,
        "context": "" # Context node will fill this in correctly by reading session_key records
    }
    
    print(f"[{event.channel}] Event received. Routing to agent {route.agent_id} (Session: {session_key})")
    
    try:
        final_state = await agent_executor.ainvoke(initial_state)
        
        # 4. Extract result and dispatch outbound message
        last_msg = final_state["messages"][-1]
        reply_text = str(last_msg.content)
        
        plugin = get_channel_plugin(event.channel)
        if plugin:
            print(f"[{event.channel}] Sending reply: {reply_text[:50]}...")
            await plugin.send_message(session_key, reply_text)
        else:
            print(f"[{event.channel}] Error: Channel plugin not found for response.")
            
    except Exception as e:
        print(f"[{event.channel}] Agent execution failed: {e}")
