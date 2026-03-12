# OpenClaw Python Backend Rewrite

This is a complete Python-based rewrite of the OpenClaw backend, designed for high performance, strict context management, and local model inference (Ollama/llama.cpp).

## 🏗 Architecture

```mermaid
graph TD
    UI[OpenClaw Frontend UI] -->|HTTP POST /v1/chat/completions| API[Python Backend (FastAPI)]

    subgraph "Python Backend Core"
        API --> Auth[Validation]
        Auth --> CM[Context Manager]
        CM -->|Truncate History| CM
        CM -->|Forward| MC[Model Client]
    end

    MC -->|Stream/Rest| OLLAMA[Ollama (Local)]
    MC -->|Stream/Rest| LLAMA[llama.cpp (Local)]
    MC -->|Stream/Rest| OAI[OpenAI (API)]

    style API fill:#f9f,stroke:#333,stroke-width:2px
    style CM fill:#bbf,stroke:#333,stroke-width:2px
    style OLLAMA fill:#bfb,stroke:#333,stroke-width:2px
```

**Key Components:**

1. **Frontend**: The original OpenClaw UI (React/Vite).
2. **Backend**: FastAPI server providing an OpenAI-compatible API (`/v1/chat/completions`).
3. **Context Manager**: Enforces strict token limits (default 16384) by truncating old messages while preserving the system prompt.
4. **Model Client**: Universal client for Ollama, llama.cpp, and OpenAI.

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** or **llama.cpp server** running locally.
- **Node.js** (for running the frontend, if not already built).

### 1. Installation & Setup

We provide a **one-click startup script** that sets up a virtual environment and installs dependencies.

```bash
cd python-backend
chmod +x start.sh
./start.sh
```

This will start the backend server at `http://0.0.0.0:8000`.

### 2. Configuration (`config.json`)

Edit `python-backend/config.json` to match your hardware and model preference.

**Recommended Config for RTX 5090 (32GB VRAM) + Qwen3.5 3.5B:**

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "max_context_tokens": 32768,
  "history_retention_rounds": 20,
  "model_name": "qwen2.5-3b-instruct",
  "backend_type": "ollama",
  "ollama_base_url": "http://localhost:11434",
  "system_prompt": "You are a helpful, smart, and efficient AI assistant..."
}
```

_Note: With 32GB VRAM, you can easily handle 32k context for a 3B model. Increase `max_context_tokens` if desired._

### 3. Running the Frontend

Update your OpenClaw Frontend configuration to point to the new Python backend.
Typically, you set an environment variable or config setting in the UI:

- **API Base URL**: `http://localhost:8000/v1`
- **API Key**: (Web blank or "sk-dummy")

If the frontend is built with Vite, you might need to proxy requests or set `VITE_API_BASE_URL` (check your frontend docs).

## 🛠 Features

- **Strict Context Limit**: Automatically removes the oldest messages to stay within `max_context_tokens`.
- **System Prompt Integrity**: The system prompt is never removed during truncation.
- **Streaming Support**: Full SSE (Server-Sent Events) support for real-time typing effect.
- **Universal Backend**: Switch between Ollama, llama.cpp, and OpenAI just by changing `backend_type` in `config.json`.

## 📂 Project Structure

```
python-backend/
├── config.py           # Configuration loader (JSON/Env)
├── config.json         # Default configuration file
├── context_manager.py  # Token counting and message truncation logic
├── main.py             # FastAPI application entry point
├── model_client.py     # Async client for LLM backends
├── requirements.txt    # Python dependencies
├── start.sh            # One-click startup script
└── README.md           # This file
```
