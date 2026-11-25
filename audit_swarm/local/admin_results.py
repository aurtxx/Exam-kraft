import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit
import websocket

root = Path("audit_swarm")
role = "AGENT-ADMIN"
tenant = "exam-kraft-swarm"
base = "http://127.0.0.1:8000"
conn = websocket.create_connection("ws://127.0.0.1:50958/session", timeout=55, suppress_origin=True)
seq = 0

def call(method, params):
    global seq
    seq += 1
    conn.send(json.dumps({"id": seq, "method": method, "params": params}))
    while True:
        msg = json.loads(conn.recv())
        if msg.get("id") == seq:
            if msg["type"] == "error":
                raise RuntimeError(f"{method}: {msg['message']}")
            return msg["result"]

def evaluate(expr):
    result = call("script.evaluate", {"expression": expr, "target": {"context": context}, "awaitPromise": True})
    if result["type"] != "success":
        raise RuntimeError("Browser evaluation failed")
    return json.loads(result["result"]["value"])

def log(action, status, code, note):
    now = datetime.now(timezone.utc).isoformat()
    with (root / f"agent_{role}.log").open("a") as out:
        out.write(f"{now} | {role} | {action} | {status} | {code} | {note}\n")

def network(method, path, body, status, excerpt):
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(body, sort_keys=True).encode()
    with (root / "network" / role / "requests.ndjson").open("a") as out:
        out.write(json.dumps({"timestamp":now, "method":method,"url":base+path,"request_body_hash":hashlib.sha256(payload).hexdigest(),"response_status":status,"response_body_excerpt":excerpt[:200]})+"\n")

def admin_form(path, fields, action):
    data = json.dumps(fields)
    target = json.dumps(path)
    result = evaluate(f"""(async () => {{
        const path = {target}, fields = {data};
        const page = await fetch(path);
        const html = new DOMParser().parseFromString(await page.text(), 'text/html');
        const csrf = html.querySelector('input[name=csrfmiddlewaretoken]');
        if (!csrf) return JSON.stringify({{method:'GET', status: page.status, url: new URL(page.url).pathname, errors:[html.querySelector('#summary h1')?.textContent,html.querySelector('.exception_value')?.textContent?.slice(0,180), 'Missing CSRF form field'].filter(Boolean)}});
        const body = new URLSearchParams({{...fields, csrfmiddlewaretoken: csrf.value}});
        const result = await fetch(path, {{method:'POST', body}});
        const resultHtml = new DOMParser().parseFromString(await result.text(), 'text/html');
        const errors = [...resultHtml.querySelectorAll('.errornote,.errorlist')].map(x=>x.innerText || x.textContent);
        return JSON.stringify({{method:'POST', status: result.status, url: new URL(result.url).pathname, errors}});
    }})()""")
    ok = result["url"] != urlsplit(path).path and not result["errors"]
    network(result["method"], path, fields if result["method"] == "POST" else None, result["status"], "Redirected" if ok else "; ".join(result["errors"]))
    log(action, "PASS" if ok else "FAIL", result["status"], result["url"] + (" " + "; ".join(result["errors"]) if not ok else ""))
    if not ok:
        raise RuntimeError(f"{action} failed")

def api(method, path, body=None, *, expected=201, action):
    opts = {"method": method, "headers": {"Content-Type": "application/json", "X-Tenant-ID": tenant}}
    if csrf:
        opts["headers"]["X-CSRFToken"] = csrf
    if body is not None:
        opts["body"] = json.dumps(body)
    expr = f"""(async()=> {{
        const response = await fetch({json.dumps(path)}, {json.dumps(opts)});
        let data;
        try {{ data = await response.json(); }} catch {{ data = {{}}; }}
        return JSON.stringify({{status: response.status, data}});
    }})()"""
    result = evaluate(expr)
    status, data = result["status"], result["data"]
    ok = status == expected
    excerpt = "" if path.endswith("/auth/login/") else json.dumps({k:data[k] for k in ("status","id","code","message") if k in data})
    network(method, path, body, status, excerpt)
    log(action, "PASS" if ok else "FAIL", status, excerpt or ("authenticated" if ok else "authentication rejected"))
    if not ok:
        raise RuntimeError(f"{action} returned {status}")
    return data

def seeded_admin_password():
    tree = ast.parse(Path("backend/apps/organizations/management/commands/seed_demo_data.py").read_text())
    return next(
        node.value.values[-1].value for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "super_pw"
    )

def write_private(path, data):
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w") as out:
        json.dump(data, out, indent=2)
        out.write("\n")


csrf = None
windows = json.loads((root / "fixtures/published_windows.json").read_text())
exams = windows["published"]
expected = {"11-PCM":3, "11-PCB":3, "12-PCM":2, "12-PCB":2}
assert set(exams) == set(expected)
closed = datetime.now(timezone.utc) >= datetime.fromisoformat(windows["end_window"])
call("session.new", {"capabilities": {}})
context = call("browsingContext.getTree", {})["contexts"][0]["context"]
call("browsingContext.navigate", {"context":context,"url":base+"/admin/","wait":"interactive"})
csrf = evaluate("""JSON.stringify(document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1])""")
assert csrf, "Missing CSRF cookie in Django admin session"
evidence = {"window_closed":closed,"exams":{}}
for suffix, exam_id in exams.items():
    name = f"EXAM-{suffix}"
    path = f"/admin/engine/examinationattempt/?q={name}"
    result = evaluate("""(async()=> {
        const res = await fetch(""" + json.dumps(path) + """);
        const doc = new DOMParser().parseFromString(await res.text(), "text/html");
        const rows = [...doc.querySelectorAll('#result_list tbody tr')].map(row =>
            Object.fromEntries(['id','user','examination','status','tab_switch_count'].map(field => [
                field, row.querySelector('.field-' + field)?.textContent.trim()
            ])));
        return JSON.stringify({status:res.status, path:new URL(res.url).pathname, rows});
    })()""")
    assert result["status"] == 200 and result["path"] == "/admin/engine/examinationattempt/", "Admin attempt list unavailable"
    rows = result["rows"]
    for row in rows:
        assert name in row["examination"]
    final_count = sum(row["status"].lower() in ("submitted","auto submitted","auto-submitted","auto_submitted") for row in rows)
    ready = closed and final_count == expected[suffix] and len(rows) == expected[suffix]
    evidence["exams"][suffix] = {"expected":expected[suffix], "final_count":final_count, "ready":ready, "attempts":rows}
    log(f"MONITOR-{name}","PASS" if ready else "PENDING",200,f"window_closed={closed} final={final_count}/{expected[suffix]} total={len(rows)}")
    print(f"{name}: window_closed={closed}, finalized={final_count}/{expected[suffix]}", flush=True)
write_private(root / "fixtures" / "phase4_evidence.json", evidence)
if os.environ.get("SWARM_PUBLISH_RESULTS_APPROVED") == "yes":
    for suffix, exam_id in exams.items():
        record = evidence["exams"][suffix]
        if not record["ready"]:
            continue
        path = f"/api/v1/analytics/examinations/{exam_id}/publish/"
        result = api("POST", path, {}, expected=200, action=f"PUBLISH-RESULTS-{suffix}")
        record["publication"] = result
        write_private(root / "fixtures" / "phase4_evidence.json", evidence)
        assert result["published_count"] == expected[suffix]
        print(f"EXAM-{suffix}: published {result['published_count']} results", flush=True)
call("browser.close", {})
conn.close()
