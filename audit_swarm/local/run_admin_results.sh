#!/bin/zsh
set -eu
/Applications/Zen.app/Contents/MacOS/zen --headless --no-remote --profile "$PWD/audit_swarm/profiles/AGENT-ADMIN" --remote-debugging-port 50958 about:blank >> audit_swarm/console/AGENT-ADMIN/browser.log 2>&1 &
zen_pid=$!
trap 'kill "$zen_pid" 2>/dev/null || true' EXIT
for i in {1..20}; do
    if lsof -nP -iTCP:50958 -sTCP:LISTEN >/dev/null; then break; fi
    sleep 1
done
.venv/bin/python -u audit_swarm/local/admin_results.py
