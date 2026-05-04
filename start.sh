#!/bin/bash
#
# Local Agent Server - Start Script
#
# Usage: ./start.sh [port]
#

set -e

# Configuration
PORT=${1:-8000}
HOST="0.0.0.0"

# Load environment variables if .env exists
if [ -f "$(dirname "$0")/local_agent_server/.env" ]; then
    echo "Loading environment from .env..."
    set -a
    source "$(dirname "$0")/local_agent_server/.env"
    set +a
fi

# Set defaults if not provided
LLM_PROVIDER=${LLM_PROVIDER:-openrouter}
LLM_MODEL=${LLM_MODEL:-openrouter/google/gemini-2.0-flash-001}
AUTH_ENABLED=${AUTH_ENABLED:-false}
OPENHANDS_SUPPRESS_BANNER=${OPENHANDS_SUPPRESS_BANNER:-1}

cd "$(dirname "$0")"

echo "============================================"
echo "  Local Agent Server"
echo "============================================"
echo "  LLM: $LLM_PROVIDER / $LLM_MODEL"
echo "  Port: $PORT"
echo "  Auth: $AUTH_ENABLED"
echo "============================================"

# Check if API key is set
if [ -z "$OPENROUTER_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: No API key set. Set OPENROUTER_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY"
    echo ""
fi

# Start the server
python -m uvicorn local_agent_server.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload

echo "Server stopped."