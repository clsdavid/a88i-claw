import json
import httpx
from typing import AsyncGenerator, List, Dict, Any, Optional
from ..config.manager import settings

class ModelClient:
    def __init__(self):
        self.backend = settings.backend_type.lower()
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat_completions(self, messages: List[Dict[str, Any]], stream: bool = False, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completions from the configured backend.
        
        Args:
            messages: List of message dicts (role, content)
            stream: Whether to stream the response
            kwargs: Additional arguments to pass to the backend API (e.g. tools, tool_choice)
        
        Yields:
            Chunks of generated response (dict containing delta or full message)
        """
        
        url = ""
        headers = {}
        payload = {}

        # Default payload construction
        if "messages" not in payload: # Payload not pre-filled
            payload = {
                "model": settings.model_name,
                "messages": messages,
                "stream": stream,
            }

        # Backend-specific adjustments
        if self.backend == "ollama":
            base_url = settings.ollama_base_url.rstrip("/")
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload["options"] = {"num_ctx": settings.max_context_tokens}
            if "max_tokens" not in kwargs:
                 payload["max_tokens"] = settings.max_generate_tokens
        
        elif self.backend == "llama_cpp":
            base_url = settings.llama_cpp_base_url.rstrip("/")
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if "max_tokens" not in kwargs:
                 payload["max_tokens"] = settings.max_generate_tokens

        elif self.backend == "openai":
            base_url = settings.openai_base_url.rstrip("/")
            url = f"{base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.openai_api_key}"
            }
            if "max_tokens" not in kwargs:
                 payload["max_tokens"] = settings.max_generate_tokens

        elif self.backend == "deepseek":
            base_url = settings.deepseek_base_url.rstrip("/")
            url = f"{base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.deepseek_api_key}"
            }
            if "max_tokens" not in kwargs:
                 payload["max_tokens"] = settings.max_generate_tokens
        
        # Merge kwargs into payload (tools, tool_choice, temperature, etc.)
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        print(f"ModelClient: Sending request to {url}...")
        try:
            if stream:
                # Use a specific timeout for the stream request to differentiate connect vs read issues
                timeout = httpx.Timeout(120.0, connect=5.0)
                async with self.client.stream("POST", url, json=payload, headers=headers, timeout=timeout) as response:
                    print(f"ModelClient: Connected. Status: {response.status_code}")
                    if response.status_code != 200:
                        error_text = await response.read()
                        print(f"ModelClient: Error response: {error_text}")
                        yield {"error": f"Error: {response.status_code} - {error_text.decode()}"}
                        yield {"content": f"**Error: {response.status_code}** - {error_text.decode()}"}
                        return

                    print("ModelClient: Streaming lines...")
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                print("ModelClient: Stream DONE")
                                break
                            try:
                                chunk = json.loads(data)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    if delta:
                                        yield delta
                            except json.JSONDecodeError:
                                print(f"ModelClient: JSON Error in chunk: {data}")
                                pass
            else:
                # Non-streaming request
                print("ModelClient: Non-streaming request...")
                response = await self.client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    yield {"error": f"Error: {response.status_code} - {response.text}"}
                    return
                # Return the full JSON response as a single yielded item
                yield response.json()

        except httpx.ConnectError as e:
            print(f"ModelClient: Connection failed: {e}")
            errmsg = f"Connection Error: Could not connect to {self.backend} at {url}. Is it running?"
            yield {"error": errmsg}
            yield {"content": f"**{errmsg}**"}
        except httpx.TimeoutException as e:
            print(f"ModelClient: Timeout: {e}")
            errmsg = "Connection Error: Request timed out."
            yield {"error": errmsg}
            yield {"content": f"**{errmsg}**"}
        except Exception as e:
            print(f"ModelClient: Exception: {e}")
            yield {"error": f"Connection Error: {str(e)}"}
            yield {"content": f"**Connection Error:** {str(e)}"}

# Singleton instance
model_client = ModelClient()
