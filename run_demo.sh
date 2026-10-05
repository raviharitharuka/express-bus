#!/usr/bin/env bash
# Start the ExpressBus demo: backend on :8000, frontend on :3000, demo clock pinned so drivers are on shift.
#
#   ./run_demo.sh                      # synthetic demo data
#   DATA_SOURCE=gtfs ./run_demo.sh     # real VAG trips (synthetic roster)
#
# Defaults can be overridden with environment variables: DATA_SOURCE, DEMO_DATE, DEMO_TIME,
# OPTIMIZE_TIME_LIMIT_S. They take precedence over backend/.env. Ctrl+C stops both servers.

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"

export DATA_SOURCE="${DATA_SOURCE:-synthetic}"
if [[ -z "${DEMO_DATE:-}" ]]; then
  # A weekday inside each dataset's calendar: synthetic covers 2026-10-01..30, gtfs is cut for 2026-07-01.
  if [[ "$DATA_SOURCE" == "gtfs" ]]; then DEMO_DATE=2026-07-01; else DEMO_DATE=2026-10-05; fi
fi
export DEMO_DATE
export DEMO_TIME="${DEMO_TIME:-09:15}"  # mid-morning: split-shift drivers are idle, emergencies get a driver

BACKEND_PORT=8000
FRONTEND_PORT=3000
LOG_DIR="$ROOT/.demo-logs"
mkdir -p "$LOG_DIR"

fail() { echo "ERROR: $*" >&2; exit 1; }
port_busy() { python3 -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', $1)) == 0 else 1)"; }
wait_for() {  # url, seconds
  for _ in $(seq 1 "$2"); do curl -sf -o /dev/null "$1" && return 0; sleep 1; done
  return 1
}

command -v python3 >/dev/null || fail "python3 not found"
command -v npm >/dev/null || fail "npm not found (install Node.js)"
command -v curl >/dev/null || fail "curl not found"
port_busy "$BACKEND_PORT" && fail "port $BACKEND_PORT is in use: stop the other backend first"
port_busy "$FRONTEND_PORT" && fail "port $FRONTEND_PORT is in use: stop the other frontend first"

if [[ ! -x backend/.venv/bin/uvicorn ]]; then
  echo "Setting up the backend (first run)..."
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [[ ! -d frontend/node_modules ]]; then
  echo "Installing frontend packages (first run)..."
  (cd frontend && npm install --no-fund --no-audit)
fi

PIDS=()
cleanup() {
  trap - EXIT INT TERM
  echo; echo "Stopping demo..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend  (DATA_SOURCE=$DATA_SOURCE, DEMO_DATE=$DEMO_DATE, DEMO_TIME=$DEMO_TIME)..."
(cd backend && exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT") >"$LOG_DIR/backend.log" 2>&1 &
PIDS+=($!)
wait_for "http://127.0.0.1:$BACKEND_PORT/health" 60 || fail "backend didn't start; see $LOG_DIR/backend.log"

echo "Starting frontend..."
(cd frontend && exec npm run dev -- --port "$FRONTEND_PORT") >"$LOG_DIR/frontend.log" 2>&1 &
PIDS+=($!)

# Warm up while the frontend compiles: the first /optimize also fills the fallback cache used if a
# later solve times out, and the frontend's Optimization page sends exactly these requests.
for overtime in true false; do
  curl -sf -o /dev/null -X POST "http://127.0.0.1:$BACKEND_PORT/optimize" \
    -H "Content-Type: application/json" -d "{\"allowOvertime\": $overtime}" || echo "  (warm-up /optimize failed; see $LOG_DIR/backend.log)"
done
curl -sf -o /dev/null "http://127.0.0.1:$BACKEND_PORT/dashboard" || true

wait_for "http://127.0.0.1:$FRONTEND_PORT" 120 || fail "frontend didn't start; see $LOG_DIR/frontend.log"

cat <<EOF

  ExpressBus demo is running
  --------------------------
  App:       http://localhost:$FRONTEND_PORT
  Admin:     http://localhost:$FRONTEND_PORT/admin
  API docs:  http://localhost:$BACKEND_PORT/docs
  Health:    $(curl -s "http://127.0.0.1:$BACKEND_PORT/health")
  Logs:      $LOG_DIR/

  Press Ctrl+C to stop.
EOF

wait
