import os
import json
from dataclasses import dataclass
from typing import Optional

CONFIG_FILE = "config.json"

@dataclass
class Config:
    # Server settings
    host: str = "0.0.0.0"
    port: int = 18789
    
    # Context settings
    max_context_tokens: int = 16384  # Total context window (Input + Output)
    max_generate_tokens: int = 2048  # Reserve for generation
    history_retention_rounds: int = 20  # Keep last N rounds effectively
    
    # Token Optimization
    truncate_tool_outputs: bool = True
    memory_max_lines: int = 50 # Max lines to display for file reads/memory
    
    # Model settings
    model_name: str = "qwen2.5-3b-instruct"  # Default for Ollama/local
    backend_type: str = "ollama"  # ollama, llama_cpp, openai
    
    # Backend URLs
    ollama_base_url: str = "http://localhost:11434"
    llama_cpp_base_url: str = "http://localhost:8080"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # System Prompt
    system_prompt: str = (
        "You are a helpful, smart, and efficient AI assistant. "
        "You utilize the Qwen3.5 3.5B model running locally. "
        "Keep your answers concise and accurate."
    )

def load_config() -> Config:
    """Load configuration from JSON file or return defaults."""
    config = Config()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                # Update config with file data
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except Exception as e:
            print(f"Error loading config.json: {e}, using defaults.")
    return config

# Global config instance
settings = load_config()
