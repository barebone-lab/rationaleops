#!/bin/bash
set -e

# RationaleOps — Launch with live DeepSeek LLM
# Double-click this file to start both backend and frontend.
# The browser opens automatically once the frontend is ready.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---- Terminal colours ----
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down…${NC}"
  kill $API_PID 2>/dev/null || true
  kill $DASHBOARD_PID 2>/dev/null || true
  wait $API_PID 2>/dev/null || true
  wait $DASHBOARD_PID 2>/dev/null || true
  echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

# ---- Backend (FastAPI) ----
echo -e "${BLUE}▸ Starting RationaleOps API (uv run rationaleops-api)…${NC}"
uv run rationaleops-api &
API_PID=$!

# Wait until the API responds
echo -n "   Waiting for API "
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo ""
    break
  fi
  echo -n "."
  sleep 1
done
echo ""

if ! kill -0 $API_PID 2>/dev/null; then
  echo -e "${YELLOW}⚠ API failed to start — check the terminal output above.${NC}"
  exit 1
fi

HEALTH=$(curl -s http://127.0.0.1:8000/api/health)
echo -e "${GREEN}✓ API ready:${NC} $(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'deepseek_configured={d[\"deepseek_configured\"]}')" 2>/dev/null || echo "$HEALTH")"

# ---- Frontend (Next.js / vinext) ----
echo ""
echo -e "${BLUE}▸ Starting dashboard (npm run dev)…${NC}"
NEXT_PUBLIC_RATIONALEOPS_API_URL=http://127.0.0.1:8000 npm --prefix web run dev &
DASHBOARD_PID=$!

echo -n "   Waiting for dashboard "
for i in $(seq 1 30); do
  if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo ""
    break
  fi
  echo -n "."
  sleep 1
done
echo ""

if ! kill -0 $DASHBOARD_PID 2>/dev/null; then
  echo -e "${YELLOW}⚠ Dashboard failed to start — check the terminal output above.${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Dashboard ready at http://localhost:3000${NC}"

# ---- Open browser ----
open http://localhost:3000

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  RationaleOps is running!${NC}"
echo -e "${GREEN}  Backend:  http://127.0.0.1:8000${NC}"
echo -e "${GREEN}  Frontend: http://localhost:3000${NC}"
echo -e "${GREEN}  LLM:      DeepSeek V4-Pro (live)${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait forever until Ctrl+C
wait
