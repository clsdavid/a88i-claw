import json
import httpx
from typing import AsyncGenerator, List, Dict, Any, Optional
from config import settings

class ModelClient:
    def __init__(self):
        self.backend = settings.backend_type.lower()
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat_completions(self, messages: List[Dict[str, Any]], stream: bool = False, **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream chat completions from the configured backend.
        
        Args:
            messages: List of message dicts (role, content)
            stream: Whether to stream the response
            kwargs: Additional arguments to pass to the backend API
        
        Yields:
            Chunks of generated text
        """
        
        url = ""
        headers = {}
        payload = {}

        if self.backend == "ollama":
            # Use Ollama native API /api/chat or strict /v1/chat/completions
            # We'll use /v1/chat/completions for compatibility if available,
            # but standard Ollama setup supports it.
            base_url = settings.ollama_base_url.rstrip("/")
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": settings.model_name,
                "messages": messages,
                "stream": stream,
                # Use settings.max_generate_tokens for output (generation limit)
                "max_tokens": settings.max_generate_tokens,
                # Pass context window size to Ollama via options for allocation
                "options": {
                    "num_ctx": settings.max_context_tokens
                }
            }
        
        elif self.backend == "llama_cpp":
            base_url = settings.llama_cpp_base_url.rstrip("/")
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": settings.model_name, # Often required but ignored by llama.cpp server
                "messages": messages,
                "stream": stream,
                "max_tokens": settings.max_generate_tokens,
            }

        elif self.backend == "openai":
            base_url = settings.openai_base_url.rstrip("/")
            url = f"{base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.openai_api_key}"
            }
            payload = {
                "model": settings.model_name,
                "messages": messages,
                "stream": stream,
                "max_tokens": settings.max_generate_tokens
            }
        
        # Merge kwargs into payload, removing None values
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        try:
            async with self.client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.read()
                    yield f"Error: {response.status_code} - {error_text.decode()}"
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            yield f"Connection Error: {str(e)}"

    async def list_models(self):
        """List available models if backend supports it"""
        pass
