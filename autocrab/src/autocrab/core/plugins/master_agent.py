import httpx
from autocrab.core.plugins.loader import skill
from autocrab.core.models.config import settings

@skill("delegate_to_master", "Delegate a complex, ambiguous task to the centralized Master Agent (agent.test) for deep resolution.")
async def delegate_to_master(task_description: str) -> str:
    """
    This skill implements the architecture requirement to allow AutoCrab instances
    to delegate highly complex queries up to the central `agent.test` hive mind.
    """
    master_url = settings.features.master_agent_url
    if not master_url:
        return "Error: MASTER_AGENT_URL is not configured."
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{master_url}/v1/delegate",
                json={"task": task_description},
                timeout=15.0
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", "Delegated successfully, but no direct result returned.")
            else:
                return f"Master Agent returned error: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Failed to contact Master Agent: {str(e)}"
