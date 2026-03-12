from .methods import system, config, chat, sessions, memory, agents

METHOD_HANDLERS = {
    # System
    "ping": system.handle_ping,
    "health": system.handle_health,
    "channels.status": system.handle_channels_status,
    "cron.status": system.handle_cron_status,
    "cron.list": system.handle_cron_list,
    "cron.runs": system.handle_cron_runs,
    "node.list": system.handle_node_list,
    "device.pair.list": system.handle_device_pair_list,

    # Config
    "config.get": config.handle_config_get,
    "config.schema": config.handle_config_schema,
    "config.schema.lookup": config.handle_config_schema_lookup,
    "models.list": config.handle_models_list,

    # Chat
    "chat.history": chat.handle_chat_history,
    "chat.send": chat.handle_chat_send,

    # Sessions
    "sessions.list": sessions.handle_sessions_list,

    # Memory
    "memory.search": memory.handle_memory_search,
    "doctor.memory.status": memory.handle_doctor_memory_status,

    # Agents
    "agents.list": agents.handle_agents_list,
    "agent.identity.get": agents.handle_agent_identity_get,
    "tools.catalog": agents.handle_tools_catalog,
}

def get_handler(method_name: str):
    return METHOD_HANDLERS.get(method_name)
