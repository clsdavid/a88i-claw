from typing import List, Dict, Any
import logging
from config import settings

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
    if HAS_TIKTOKEN and ENCODING:
        return len(ENCODING.encode(text))
    else:
        # Heuristic: 1 token is roughly 4 characters
        return max(1, len(text) // 4)

def truncate_context(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Truncates the message history to fit within context limits.
    Ensures input_tokens + max_generate_tokens <= max_context_tokens.
    Always maintains the system message at the start if present.
    Removes oldest messages first.
    """
    if not messages:
        return []

    # Calculate available space for input
    # max_context_tokens (e.g. 16384) - max_generate_tokens (e.g. 2048) = ~14336 for input
    available_tokens = settings.max_context_tokens - settings.max_generate_tokens
    if available_tokens < 100:
        logger.warning(f"Warning: Very small context window ({available_tokens}). Check config.")
        available_tokens = 512 # Fallback minimum

    # Identify system message
    system_message = None
    user_assistant_messages = []
    
    for msg in messages:
        if msg.get("role") == "system":
            system_message = msg
        else:
            # OPTIMIZATION: Check for tool/function outputs and truncate
            if settings.truncate_tool_outputs and msg.get("role") in ["tool", "function"]:
                content = msg.get("content", "")
                if isinstance(content, str):
                    lines = content.splitlines()
                    if len(lines) > settings.memory_max_lines:
                        # Keep first N lines
                        truncated_lines = lines[:settings.memory_max_lines]
                        footer = f"\n... [Truncated by Backend: {len(lines) - settings.memory_max_lines} lines omitted. Use read_file with line range if needed.]"
                        
                        # Create copy to avoid mutating original request object deeply if shared
                        new_msg = msg.copy()
                        new_msg["content"] = "\n".join(truncated_lines) + footer
                        msg = new_msg
            
            user_assistant_messages.append(msg)
            
    # Limit by number of rounds (Configurable history_retention_rounds)
    if settings.history_retention_rounds > 0:
        max_msgs = settings.history_retention_rounds * 2
        if len(user_assistant_messages) > max_msgs:
            user_assistant_messages = user_assistant_messages[-max_msgs:]

    # Calculate token count so far
    current_tokens = 0
    if system_message:
        current_tokens += get_token_count(system_message.get("content", ""))
    
    # We will rebuild the list of messages in reverse (newest first)
    kept_messages = []
    
    # Process from newest to oldest
    for msg in reversed(user_assistant_messages):
        content = msg.get("content", "")
        # Handle cases where content is a list (multimodal)
        if isinstance(content, list):
            # Very rough estimate for multimodal content if string conversion is complex
            text_content = ""
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                   text_content += item['text']
            token_count = get_token_count(text_content) + 100 # buff for images
        else:
            token_count = get_token_count(str(content))
            
        if current_tokens + token_count > available_tokens:
            logger.info(f"Truncated message history to fit {available_tokens} tokens.")
            break
            
        current_tokens += token_count
        kept_messages.insert(0, msg)
        
    # Reassemble: System + Truncated History
    final_messages = []
    if system_message:
        final_messages.append(system_message)
    
    final_messages.extend(kept_messages)
    
    return final_messages
