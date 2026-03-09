#!/bin/bash
set -e

# Default model
MODEL="qwen3.5:35b"

# Check dependencies
if ! command -v docker >/dev/null; then
    echo "Error: docker is required."
    exit 1
fi

# Parse arguments
if [ -n "$1" ]; then
    MODEL="${1//[\[\]]/}"
fi

# Set default directories
AUTOCRAB_CONFIG_DIR="${AUTOCRAB_CONFIG_DIR:-$HOME/.autocrab}"
AUTOCRAB_WORKSPACE_DIR="${AUTOCRAB_WORKSPACE_DIR:-$HOME/.autocrab/workspace}"
export AUTOCRAB_CONFIG_DIR
export AUTOCRAB_WORKSPACE_DIR

# Write environment variables to .env for future Docker Compose commands
cat <<EOF > .env
AUTOCRAB_CONFIG_DIR=$AUTOCRAB_CONFIG_DIR
AUTOCRAB_WORKSPACE_DIR=$AUTOCRAB_WORKSPACE_DIR
EOF

# Ensure directories exist
mkdir -p "$AUTOCRAB_CONFIG_DIR" "$AUTOCRAB_WORKSPACE_DIR"

# Generate or reuse gateway token
if [ -z "$AUTOCRAB_GATEWAY_TOKEN" ]; then
    # Try to read from config file first
    CONFIG_FILE="$AUTOCRAB_CONFIG_DIR/autocrab.json"
    if [ -f "$CONFIG_FILE" ]; then
        TOKEN=$(grep -o '"gatewayToken": *"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
        if [ -n "$TOKEN" ]; then
            export AUTOCRAB_GATEWAY_TOKEN="$TOKEN"
        fi
    fi
fi

if [ -z "$AUTOCRAB_GATEWAY_TOKEN" ]; then
    echo "⚠️  AUTOCRAB_GATEWAY_TOKEN not found. Generating a temporary one."
    if command -v openssl >/dev/null; then
        export AUTOCRAB_GATEWAY_TOKEN=$(openssl rand -hex 16)
    else
        echo "⚠️  'openssl' not found. Using default unsafe token."
        export AUTOCRAB_GATEWAY_TOKEN="autocrab-local-dev-token"
    fi
    echo "🔑 Gateway Token: $AUTOCRAB_GATEWAY_TOKEN"
    # Append to .env
    echo "AUTOCRAB_GATEWAY_TOKEN=$AUTOCRAB_GATEWAY_TOKEN" >> .env
fi

echo "🚀 Deploying AutoCrab with local Ollama..."

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama detected at http://localhost:11434"
else
    echo "❌ Ollama is not reachable at http://localhost:11434"
    echo "   Please start Ollama and ensure it is listening on localhost."
    echo "   If running on Linux, ensure it listens on 127.0.0.1 or 0.0.0.0."
    exit 1
fi

# Check/Pull model
echo "🔍 Checking for model '$MODEL'..."
if command -v ollama >/dev/null; then
    # Use CLI if available
    if ! ollama list | grep -q "$MODEL"; then
        echo "⬇️  Pulling model '$MODEL'..."
        ollama pull "$MODEL"
    fi
else
    # Fallback to curl check
    if ! curl -s http://localhost:11434/api/tags | grep -q "$MODEL"; then
        echo "⬇️  Pulling model '$MODEL' (this may take a while)..."
        curl -s http://localhost:11434/api/pull -d "{\"name\": \"$MODEL\"}" > /dev/null
    fi
fi

# Configure environment for Docker
# Append other variables to .env
cat <<EOF >> .env
AUTOCRAB_MODEL_PROVIDER=ollama
AUTOCRAB_MODEL_ID=$MODEL
OLLAMA_BASE_URL=http://host.docker.internal:11434
# For Linux, access Ollama via host.docker.internal (requires extra_hosts) or use bridge IP
EOF

# Check if image exists, build if not
if [[ "$(docker images -q autocrab:local 2> /dev/null)" == "" ]]; then
  echo "🏗️  Image autocrab:local not found. Building..."
  docker build -t autocrab:local .
else
  echo "✅ Image autocrab:local found."
fi
export AUTOCRAB_IMAGE="autocrab:local"
echo "AUTOCRAB_IMAGE=autocrab:local" >> .env

echo "🐳 Starting Docker containers..."
echo "For Linux users: Ensure 'host.docker.internal' is supported (Docker 20.10+)."

# Bring up services
docker compose up -d --remove-orphans

echo ""
echo "✅ Deployment complete!"
echo "   Provider: ollama"
echo "   Model:    $MODEL"
echo "   Gateway:  http://localhost:18789"
echo ""
echo "Logs: docker compose logs -f"
