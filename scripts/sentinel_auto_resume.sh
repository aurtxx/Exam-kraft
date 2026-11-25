#!/usr/bin/env bash
# Sentinel Auto-Resume Script for Exam-Kraft (AGY + Codex autonomous recovery)
# Watches for idle background workers, quota expirations, or server restarts,
# automatically resuming work and logging state.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
cd "$DIR"

LOG_FILE="$DIR/audit_fix/sentinel_resume.log"
mkdir -p "$DIR/audit_fix"

echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Sentinel daemon initialized." >> "$LOG_FILE"

while true; do
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

    # 1. Check if Django backend is alive on port 8000
    if ! curl -s -f http://localhost:8000/api/v1/health/ > /dev/null 2>&1; then
        echo "[$TIMESTAMP] Backend server down. Restarting Django on port 8000..." >> "$LOG_FILE"
        cd "$DIR/backend"
        nohup .venv/bin/python manage.py runserver 0.0.0.0:8000 >> "$DIR/audit_fix/backend_stdout.log" 2>&1 &
        cd "$DIR"
    fi

    # 2. Check if Vite frontend is alive on port 5173
    if ! curl -s -f http://localhost:5173/ > /dev/null 2>&1; then
        echo "[$TIMESTAMP] Frontend server down. Restarting Vite on port 5173..." >> "$LOG_FILE"
        cd "$DIR/frontend"
        nohup npm run dev -- --host 0.0.0.0 --port 5173 >> "$DIR/audit_fix/frontend_stdout.log" 2>&1 &
        cd "$DIR"
    fi

    # 3. Check if autonomous Codex CLI session is running
    CODEX_PID=$(pgrep -f "codex exec" || true)
    if [ -z "$CODEX_PID" ]; then
        if [ ! -f "$DIR/audit_fix/codex_browser_integration_fixes.md" ]; then
            echo "[$TIMESTAMP] Codex session not active and fixes report not finished. Resuming Codex..." >> "$LOG_FILE"
            nohup "$DIR/run_codex_browser_qa.sh" >> "$DIR/audit_fix/codex_auto_resume.log" 2>&1 &
        fi
    fi

    # Sleep 60 seconds before next heartbeat check
    sleep 60
done
