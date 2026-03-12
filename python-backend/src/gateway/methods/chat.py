import json
import time
import uuid
import asyncio
from fastapi import WebSocket
from ...config.manager import settings
from ...models.client import model_client
from ...utils.context import truncate_context
import os
import aiofiles

async def handle_chat_history(websocket: WebSocket, req_id: str, params: dict):
    session_key = params.get("sessionKey")
    messages = []
    if session_key and settings.sessions_dir:
        session_file = os.path.join(settings.sessions_dir, f"{session_key}.jsonl")
        if os.path.exists(session_file):
            async with aiofiles.open(session_file, mode='r') as f:
                async for line in f:
                    if line.strip():
                        try:
                            messages.append(json.loads(line))
                        except:
                            pass

    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "messages": messages,
            "thinkingLevel": "low"
        }
    })

async def handle_chat_send(websocket: WebSocket, req_id: str, params: dict):
    session_key = params.get("sessionKey")
    user_message = params.get("message")
    
    # 1. Send ACK immediately
    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {}
    })

    # 2. Validate Session
    if not session_key:
         print("Warning: No sessionKey provided")
         return

    if session_key and settings.sessions_dir:
        # Ensure session dir
        if not os.path.exists(settings.sessions_dir):
            os.makedirs(settings.sessions_dir, exist_ok=True)
            
        session_file = os.path.join(settings.sessions_dir, f"{session_key}.jsonl")
        
        # 3. Load History
        history = []
        if os.path.exists(session_file):
            try:
                async with aiofiles.open(session_file, mode='r') as f:
                     async for line in f:
                         if line.strip():
                             try:
                                 msg_obj = json.loads(line)
                                 # Clean for model context
                                 clean_msg = {k: v for k, v in msg_obj.items() if k in ["role", "content", "name", "tool_calls"]}
                                 history.append(clean_msg)
                             except:
                                 pass
            except Exception as e:
                print(f"Error loading history: {e}")
        
        # 4. Append New User Message
        user_entry = {"role": "user", "content": user_message, "ts": int(time.time() * 1000)}
        
        # Save to file
        try:
            async with aiofiles.open(session_file, mode='a') as f:
                await f.write(json.dumps(user_entry) + "\n")
        except Exception as e:
            print(f"Error saving user message: {e}")
            return
            
        # Add to history for generation
        history.append({k: v for k, v in user_entry.items() if k in ["role", "content"]})
        
        # Inject System Prompt
        model_messages = [{"role": "system", "content": "You are a helpful AI assistant."}] + history

        # 5. Stream Response
        run_id = str(uuid.uuid4())
        full_content = ""
        seq = 0
        
        try:
            truncated_messages = truncate_context(model_messages)
            
            # Helper to send event
            async def send_event(state: str, payload_msg: dict, error_msg: str = None):
                payload = {
                     "runId": run_id,
                     "sessionKey": session_key,
                     "seq": seq,
                     "state": state,
                     "message": payload_msg
                 }
                if error_msg:
                    payload["errorMessage"] = error_msg
                
                await websocket.send_json({
                    "type": "event",
                    "event": "chat.event",
                    "payload": payload
                })

            print(f"Chat: Starting completion stream for {settings.backend_type}...")
            async for chunk in model_client.chat_completions(messages=truncated_messages, stream=True):
                 if "error" in chunk:
                     print(f"Model Error: {chunk['error']}")
                     await send_event("error", {}, chunk["error"])
                     return

                 content = chunk.get("content", "")
                 if content:
                     full_content += content
                 
                 # Send delta with FULL ACCUMULATED CONTENT (frontend requirement)
                 payload_chunk = chunk.copy()
                 payload_chunk["content"] = full_content
                 await send_event("delta", payload_chunk)
                 seq += 1

                 # Yield to event loop to ensure flush
                 await asyncio.sleep(0.001)
            
            # Send final
            await send_event("final", {"role": "assistant", "content": full_content})
            
            # Save assistant message
            assistant_entry = {"role": "assistant", "content": full_content, "ts": int(time.time() * 1000)}
            async with aiofiles.open(session_file, mode='a') as f:
                await f.write(json.dumps(assistant_entry) + "\n")
                
        except Exception as e:
            print(f"Error generation: {e}")
            # Ensure an error event is sent so the client doesn't hang
            try:
                await websocket.send_json({
                     "type": "event",
                     "event": "chat.event",
                     "payload": {
                         "runId": run_id,
                         "sessionKey": session_key,
                         "seq": seq,
                         "state": "error",
                         "errorMessage": str(e)
                     }
                })
            except:
                pass
