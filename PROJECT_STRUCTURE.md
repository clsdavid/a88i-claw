# OpenClaw Python Uplift - Project Structure

The project has been restructured to center around the new `python-backend/` core while maintaining the existing UI and documentation. The goal is to separate concerns clearly: UI (Frontend) vs Logic (Python Backend).

## 📂 Root Directory

- **`python-backend/`**: The new heart of the application. Contains all business logic, API endpoints, and model handling.
- **`ui/`**: (Existing) React/Vite frontend application. The user interface remains largely unchanged but now points to the Python API.
- **`docs/`**: (Existing) Documentation files.
- **`start.sh`**: (New) Master startup script orchestrating the Python backend (and optionally the UI).

## 🐍 Python Backend (`python-backend/`)

This directory follows a standard, flat Python project structure for clarity and ease of modification.

### Key Files

| File                     | Purpose                       | Key Responsibilities                                                                                                                                                                                      |
| :----------------------- | :---------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`main.py`**            | **Application Entry Point**   | Initializes FastAPI app, defines API routes (`/v1/chat/completions`), handles request validation, and manages server lifecycle.                                                                           |
| **`context_manager.py`** | **Core Logic: Context**       | Implements the **Strict Context Limit**. Handles token counting (via `tiktoken`), message truncation (keeping system prompt + recent history), and ensures prompts fit within the model's context window. |
| **`model_client.py`**    | **Core Logic: LLM Interface** | Acts as a unified client for Ollama, llama.cpp, and OpenAI. Handles streaming responses (SSE), error handling, and backend-specific payload formatting.                                                   |
| **`config.py`**          | **Configuration Loader**      | Loads settings from `config.json` or environment variables. Provides typed configuration objects to the rest of the application.                                                                          |
| **`config.json`**        | **User Configuration**        | The single source of truth for user settings (API keys, model names, context limits, backend URLs). Simple JSON format for easy editing.                                                                  |
| **`start.sh`**           | **Startup Script**            | Automates environment setup (`venv`), dependency installation (`pip`), and server execution (`uvicorn`).                                                                                                  |
| **`requirements.txt`**   | **Dependencies**              | Lists all Python packages required: `fastapi`, `uvicorn`, `httpx`, `tiktoken`, etc.                                                                                                                       |

## 📐 Usage & Modification

### Adding a New Model Backyard

1.  Open `python-backend/model_client.py`.
2.  Add a new condition in `chat_completions` (e.g., `elif self.backend == "groq":`).
3.  Add the backend-specific URL and payload logic.
4.  Update `config.json` to include the new backend type.

### Changing Context Logic

1.  Open `python-backend/context_manager.py`.
2.  Modify the `truncate_context` function. You can change the truncation strategy (e.g., keep the first 3 user messages instead of just the system prompt).

### Updating API Routes

1.  Open `python-backend/main.py`.
2.  Add new `@app.get` or `@app.post` decorators to define new endpoints.
3.  Implement the handler function.

## 🛠 Integration with Frontend

The frontend (in `ui/` or `dist/control-ui`) expects a standard OpenAI-compatible API. By providing `/v1/chat/completions` in `main.py`, the Python backend serves as a drop-in replacement for the original backend.

Ensure your frontend configuration (e.g., `.env` file in `ui/`) points to:

```env
VITE_API_BASE_URL=http://localhost:8000/v1
```
