#!/bin/bash
set -e

INIT_ONLY=false
if [ "$1" == "--init-only" ]; then
    INIT_ONLY=true
fi

# Directory config
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
else
    source venv/bin/activate
fi


echo "Installing requirements..."
pip -q install -r requirements.txt

if [ "$INIT_ONLY" == "true" ]; then
    echo "Environment initialized."
    echo "Dependencies installed."
    exit 0
fi

# Start backend
echo "Starting OpenClaw Python Backend on port 18789..."
# Check if port is in use and kill
if lsof -i :18789 > /dev/null; then
    echo "Port 18789 is in use. Attempting to free it..."
    fuser -k 18789/tcp || true
    sleep 1
fi

# Use uvicorn with reload for development-like feel but standard worker for stability
exec uvicorn main:app --host 0.0.0.0 --port 18789 --reload
