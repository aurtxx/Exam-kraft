from datetime import datetime, timezone
from pathlib import Path
import json
import os
import subprocess
import time

windows = json.loads(Path("audit_swarm/fixtures/published_windows.json").read_text())
close = datetime.fromisoformat(windows["end_window"])
print(f"PID {os.getpid()} waiting to publish after {close.isoformat()}", flush=True)
while (remaining := (close - datetime.now(timezone.utc)).total_seconds()) >= 0:
    time.sleep(min(remaining + 0.25, 20))
print(f"{datetime.now(timezone.utc).isoformat()} starting gated Zen publication", flush=True)
subprocess.run(["zsh", "audit_swarm/local/run_admin_results.sh"], env={**os.environ, "SWARM_PUBLISH_RESULTS_APPROVED":"yes"}, check=True)
print(f"{datetime.now(timezone.utc).isoformat()} publication command finished", flush=True)
