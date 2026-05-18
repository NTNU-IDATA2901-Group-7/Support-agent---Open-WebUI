# Load environment variables from .env
set -a
source ../.env
set +a

export CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8080"
PORT="${PORT:-8080}"
MCP_PORT="${MCP_PORT:-8000}"
MCPO_PORT="${MCPO_PORT:-8001}"

# Pre-flight: kill any orphan processes holding our ports
for port in $MCP_PORT $MCPO_PORT; do
  pid=$(lsof -ti:$port 2>/dev/null)
  if [ -n "$pid" ]; then
    echo "Killing orphan process on port $port (PID $pid)..."
    kill -9 $pid 2>/dev/null
  fi
done

# Start MCP server in background (Streamable HTTP)
echo "Starting MCP server on port $MCP_PORT..."
PYTHONPATH="." python open_webui/utils/mcp/server.py &
MCP_PID=$!

# Wait for MCP server to be ready
echo "Waiting for MCP server..."
until curl -s -o /dev/null "http://localhost:$MCP_PORT/mcp"; do
  sleep 0.5
done
echo "MCP server is ready."

# Start mcpo proxy in background (OpenAPI wrapper for Open WebUI)
echo "Starting mcpo proxy on port $MCPO_PORT..."
uvx mcpo --port "$MCPO_PORT" --server-type "streamable-http" -- "http://localhost:$MCP_PORT/mcp" &
MCPO_PID=$!

trap "kill $MCP_PID $MCPO_PID 2>/dev/null" EXIT

uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload
