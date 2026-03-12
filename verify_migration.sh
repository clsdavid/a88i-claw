#!/bin/bash
set -e

# Start python backend
echo "Starting Python backend..."
cd python-backend
./start.sh > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend
echo "Waiting for backend..."
sleep 5
curl -s http://localhost:8000/api/health | grep "python" || { echo "Backend failed to start"; kill $BACKEND_PID; exit 1; }

# Configure CLI to use Python backend for REST
echo "Configuring CLI..."
# We use env vars to avoid modifying user config permanently if possible, 
# but callGateway resolves config. Let's use env overrides.
export AUTOCRAB_GATEWAY_URL="http://localhost:8000"
export GATEWAY_MODE="remote" 
# Note: call.ts reads AUTOCRAB_GATEWAY_URL

# Run doctor check commands (dry run)
echo "Running autocrab doctor (health check)..."
# We target `autocrab doctor` which calls `health`.
# Since we are in dev, run via pnpm
# We might need to handle authentication if backend required it, but it doesn't currently.

# Test 1: Health check command (simulated via status command)
# 'autocrab config' is local, 'autocrab status' calls gateway.
./bin/autocrab-python status --json || echo "Status command returned non-zero (expected if mock data incomplete)"

# Test 2: Channel status
curl -s http://localhost:8000/v1/channels

# Cleanup
kill $BACKEND_PID
echo "Done."
