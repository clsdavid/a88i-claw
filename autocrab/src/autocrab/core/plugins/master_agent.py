import httpx
import asyncio
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
                f"{master_url}/orchestrator/query",
                json={"query": task_description},
                timeout=15.0
            )
            if resp.status_code != 200:
                return f"Master Agent returned error: {resp.status_code} - {resp.text}"
                
            data = resp.json()
            job_id = data.get("job_id")
            if not job_id:
                return "Delegated successfully, but no job_id returned."
                
            # Polling loop for job completion
            for _ in range(120):  # Poll for up to 600 seconds
                await asyncio.sleep(5.0)
                poll_resp = await client.get(
                    f"{master_url}/orchestrator/status/{job_id}",
                    timeout=5.0
                )
                if poll_resp.status_code == 200:
                    poll_data = poll_resp.json()
                    status = poll_data.get("status")
                    if status == "completed":
                        result = poll_data.get("final_output", "")
                        if isinstance(result, str):
                            return result
                        return str(result)
                    elif status == "failed":
                        return f"Master Agent job {job_id} failed."
                        
            return f"Master Agent job {job_id} is running in background. Status pending."
    except Exception as e:
        return f"Failed to contact Master Agent: {str(e)}"
