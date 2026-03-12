from typing import List, Dict, Any
import logging
from ..config.manager import settings

logger = logging.getLogger(__name__)

try:
    import tiktoken
    ENCODING = tiktoken.get_encoding("cl100k_base")  # Good approximation for most LLMs
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    ENCODING = None

def get_token_count(text: str) -> int:
    """
    Returns the number of tokens in a text string.
    Uses tiktoken if available, otherwise a heuristic (1 token ~= 4 chars).
    """
    if hasattr(text, "encode"):
        # Handle string capable objects
        pass
    else:
        text = str(text)

    if HAS_TIKTOKEN and ENCODING:
        try:
            return len(ENCODING.encode(text))
        except Exception:
             return len(text) // 4
    else:
        # Heuristic: 1 token is roughly 4 characters
        return max(1, len(text) // 4)

def truncate_context(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Truncates the message history to fit within context limits.
    Ensures input_tokens + max_generate_tokens <= max_context_tokens.
    Always maintains the system message at the start if present.
    """
    if not messages:
        return []

    # Identify system message
    system_message = None
    if messages[0].get("role") == "system":
        system_message = messages[0]
        remaining_messages = messages[1:]
    else:
        remaining_messages = messages

    # Calculate token budget
    total_allowed = settings.max_context_tokens
    reserved_for_gen = settings.max_generate_tokens
    
    # Calculate overhead (heuristic per message)
    msg_overhead = 4 

    current_tokens = 0
    if system_message:
        current_tokens += get_token_count(system_message.get("content", "")) + msg_overhead

    max_input_tokens = total_allowed - reserved_for_gen
    
    truncated = []
    
    # Add messages from the end (most recent) until full
    for msg in reversed(remaining_messages):
        content = msg.get("content", "")
        # Handle tool calls / non-string content
        if not isinstance(content, str):
            content = str(content)
            
        count = get_token_count(content) + msg_overhead
        
        if current_tokens + count > max_input_tokens:
            break
            
        current_tokens += count
        truncated.insert(0, msg)
        
    if system_message:
        truncated.insert(0, system_message)
        
    return truncated
