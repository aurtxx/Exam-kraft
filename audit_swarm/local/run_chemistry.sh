#!/bin/zsh
cd /Users/aurtx/teamwork_projects/ezexam_reconstruction
/Applications/Zen.app/Contents/MacOS/zen --headless --no-remote --profile "$PWD/audit_swarm/profiles/AGENT-TEACHER-CHEM" --remote-debugging-port 50962 about:blank > audit_swarm/local/chemistry_zen.log 2>&1 &
for i in {1..20}; do
  if rg -q 'BiDi listening' audit_swarm/local/chemistry_zen.log; then break; fi
  sleep 1
done
.venv/bin/python audit_swarm/local/chemistry_phase1.py
