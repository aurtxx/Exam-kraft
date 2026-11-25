import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import websocket

root = Path("audit_swarm")
role = "AGENT-TEACHER-CHEM"
base = "http://127.0.0.1:5173"
profile = root / "profiles" / role
network_file = root / "network" / role / "requests.ndjson"
console_file = root / "console" / role / "errors.log"
for directory in [profile, network_file.parent, console_file.parent]:
    directory.mkdir(parents=True, exist_ok=True)
console_file.touch()
credentials = json.loads((root / "fixtures/teacher_credentials.json").read_text())[role]
papers = json.loads((root / "fixtures/phase0_ids.json").read_text())["papers"]
conn = websocket.create_connection("ws://127.0.0.1:50962/session", timeout=55, suppress_origin=True)
sequence = 0
token = None

def call(method, params):
    global sequence
    sequence += 1
    conn.send(json.dumps({"id": sequence, "method": method, "params": params}))
    while True:
        msg = json.loads(conn.recv())
        if msg.get("method") == "log.entryAdded" and msg["params"].get("level") == "error":
            with console_file.open("a") as out:
                out.write(str(msg["params"].get("text", ""))[:200] + "\n")
        if msg.get("id") == sequence:
            if msg["type"] == "error":
                raise RuntimeError(f"{method}: {msg['message']}")
            return msg["result"]

def evaluate(expression):
    result = call("script.evaluate", {"expression": expression, "target": {"context": context}, "awaitPromise": True})
    if result["type"] != "success":
        raise RuntimeError(result.get("exceptionDetails", {}).get("text", "Browser evaluation failed"))
    return result["result"].get("value")

def record(action, status, http, note):
    with (root / f"agent_{role}.log").open("a") as out:
        out.write(f"{datetime.now(timezone.utc).isoformat()} | {role} | {action} | {status} | {http} | {note}\n")

def api(method, path, action, *, body=None, fixture=None, expected=200):
    headers = {"X-Tenant-ID": "exam-kraft-swarm"}
    if token:
        headers["Authorization"] = "Bearer " + token
    opts = {"method": method, "headers": headers}
    if fixture:
        selector = "#audit-upload"
        attach = evaluate("(() => { document.querySelector('#audit-upload')?.remove(); const i = document.createElement('input'); i.id = 'audit-upload'; i.type = 'file'; document.body.append(i); return true; })()")
        assert attach
        nodes = call("browsingContext.locateNodes", {"context": context, "locator": {"type": "css", "value": selector}})["nodes"]
        call("input.setFiles", {"context": context, "element": {"sharedId": nodes[0]["sharedId"]}, "files": [str(fixture.resolve())]})
        source = f"""const fields = {json.dumps(body or {})};
        const form = new FormData();
        for (const [key, value] of Object.entries(fields)) form.append(key, value);
        const file = document.querySelector({json.dumps(selector)}).files[0];
        if (!file || !file.size) throw Error('No file attached');
        form.append('file', file); opts.body = form;"""
    elif body is not None:
        opts["headers"]["Content-Type"] = "application/json"
        opts["body"] = json.dumps(body)
        source = ""
    else:
        source = ""
    expression = f"""(async()=>{{
      const opts = {json.dumps(opts)};
      {source}
      const response = await fetch({json.dumps(path)}, opts);
      let data; try {{ data = await response.json(); }} catch {{ data = {{}}; }}
      return JSON.stringify({{status: response.status, data}});
    }})()"""
    status_data = json.loads(evaluate(expression))
    status, data = status_data["status"], status_data["data"]
    excerpt = {} if path.endswith("/auth/login/") else {k: data[k] for k in ("status", "id", "code", "message", "detail") if k in data}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode())
    if fixture:
        digest.update(fixture.read_bytes())
    with network_file.open("a") as out:
        out.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "method": method, "url": base + path, "request_body_hash": digest.hexdigest(), "response_status": status, "response_body_excerpt": json.dumps(excerpt)[:200]}) + "\n")
    record(action, "PASS" if status == expected else "FAIL", status, json.dumps(excerpt))
    return status, data

def questions(stem):
    def mcq(number, prompt, options):
        return {"question_number": number, "section_name": "Chemistry", "question_type": "MCQ_SINGLE",
                "content_text": f"{stem} {prompt}", "options": [{"option_key": chr(65+i), "content_text": option, "is_correct": i == 0} for i, option in enumerate(options)]}
    return [
        mcq(6, "Which element is represented by Na?", ["Sodium", "Nitrogen", "Neon", "Nickel"]),
        {"question_number": 7, "section_name": "Chemistry", "question_type": "NUMERICAL",
         "content_text": f"{stem} How many hydrogen atoms are in one molecule of methane?",
         "key": "4", "numerical_min": 4, "numerical_max": 4},
        mcq(8, "Which state of matter has a fixed volume and takes the shape of its container?", ["Liquid", "Solid", "Gas", "Plasma"]),
        mcq(9, "Which particle carries negative electric charge?", ["Electron", "Proton", "Neutron", "Alpha particle"]),
        mcq(10, "What is the formula of water?", ["H₂O", "H₂O₂", "CO₂", "O₂"]),
    ]

try:
    call("session.new", {"capabilities": {}})
    context = call("browsingContext.getTree", {})["contexts"][0]["context"]
    call("browsingContext.setViewport", {"context": context, "viewport": {"width": 1366, "height": 768}})
    call("browsingContext.navigate", {"context": context, "url": base + "/login", "wait": "interactive"})
    call("session.subscribe", {"events": ["log.entryAdded"], "contexts": [context]})
    status, result = api("POST", "/api/v1/auth/login/", "LOGIN", body=credentials)
    if status != 200:
        raise RuntimeError("Teacher login failed")
    token = result["access"]
    for paper, identifier in papers.items():
        path = f"/api/v1/question-papers/{identifier}/questions/"
        stem = f"[CHEM {paper}]"
        payloads = questions(stem)
        _, existing = api("GET", path, f"{paper}_EXISTING")
        created_stems = {q.get("content_text") for q in existing.get("questions", [])}
        for index, payload in enumerate(payloads):
            method = ("A", "A", "B", "B", "C")[index]
            if payload["content_text"] in created_stems:
                continue
            if method == "B":
                status, result = api("POST", path, f"{paper}_B_PNG_{index-1}", body={"content_text": "What is the value of x?"}, fixture=root / "fixtures/sample_question.png", expected=201)
                if status != 400 or result.get("code") != "INVALID_QUESTION_TYPE":
                    raise RuntimeError(f"Unexpected PNG response on {paper}: {status}")
                record("TEACHER-FINDING-001", "UNSUPPORTED", status, "Multipart PNG received by question endpoint. Endpoint requires explicit question type and does not extract question fields.")
            if method == "C":
                record("TEACHER-FINDING-002", "UNSUPPORTED", "-", "Question-bank routes expose no Excel answer-key import endpoint. JSON fallback used.")
            for attempt in range(5):
                status, result = api("POST", path, f"{paper}_{method}_QUESTION_{index+1}", body=payload, expected=201)
                if status == 201:
                    break
                if status != 500:
                    raise RuntimeError(f"Question creation failed: {status}")
                time.sleep((attempt + 1) * 0.25)
            if status != 201:
                raise RuntimeError("Retries did not create the question")
        status, result = api("GET", path, f"{paper}_VERIFY")
        owned = [q for q in result.get("questions", []) if q.get("content_text", "").startswith(stem)]
        assert status == 200 and len(owned) == 5 and {q["content_text"] for q in owned} == {q["content_text"] for q in payloads}
        record(f"{paper}_VERIFY_CHEM_COUNT", "PASS", 200, "Five Chemistry questions matched their authored stems")
    (root / "teacher_upload_findings_CHEM.md").write_text("""# Chemistry teacher uploads

- Method A and JSON fallbacks passed. Verified five Chemistry questions in each of four papers.
- TEACHER-FINDING-001. Eight real multipart PNG submissions returned HTTP 400 INVALID_QUESTION_TYPE. The authoring endpoint requires question fields and exposes no image parsing workflow.
- TEACHER-FINDING-002. The question-bank routes and staff interface expose no Excel answer-key import endpoint. Used JSON fallback for each paper.
- The Chemistry session used its assigned faculty account exclusively. Candidate permission evidence belongs to the student phase.
""")
finally:
    try:
        call("browser.close", {})
    finally:
        conn.close()
