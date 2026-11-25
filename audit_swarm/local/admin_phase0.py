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
    if token:
        opts["headers"]["Authorization"] = f"Bearer {token}"
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

token = None
call("session.new", {"capabilities": {}})
context = call("browsingContext.getTree", {})["contexts"][0]["context"]
call("browsingContext.navigate", {"context":context,"url":base+"/admin/login/","wait":"interactive"})
admin_auth = {"username":"superadmin@ezexam.local","password":seeded_admin_password()}
admin_form("/admin/login/?next=/admin/", {**admin_auth, "next":"/admin/"}, "DJANGO_ADMIN_LOGIN")

admin_form("/admin/organizations/organization/add/", {"name":"Exam-kraft Swarm School", "slug":tenant, "settings":"{}", "is_active":"on", "_save":"Save"}, "CREATE_ORGANIZATION")
token = api("POST", "/api/v1/auth/login/", admin_auth, expected=200, action="ADMIN_API_LOGIN")["access"]
write_private(root / "tokens.json", {role: token})
cohorts = {"11-PCM":[1,2,3],"11-PCB":[4,5,6],"12-PCM":[7,8],"12-PCB":[9,10]}
student_credentials = {}
teacher_credentials = {}
batches, papers, exams = {}, {}, {}
for suffix, students in cohorts.items():
    name = "BATCH-"+suffix
    batch = api("POST", "/api/v1/organizations/batches/", {"name":name,"code":name,"stream":"JEE_MAIN" if suffix.endswith("PCM") else "NEET"}, action="CREATE_"+name)
    batches[suffix] = batch["id"]
    for n in students:
        student = f"AGENT-S-{n:02d}"
        username = f"swarm-s-{n:02d}@exam-kraft-swarm.test"
        creds = {"username":username,"password":secrets.token_urlsafe(24)}
        result = api("POST", "/api/v1/users/students/", {**creds,"email":username,"name":student,"roll_number":f"SWARM-{n:02d}","batch_id":batch["id"]}, action="CREATE_"+student)
        assert result["student"]["batch_name"] == name
        student_credentials[student] = creds
write_private(root / "fixtures" / "student_credentials.json", student_credentials)
for abbrev, subject in {"PHY":"Physics","CHEM":"Chemistry","BIO":"Biology"}.items():
    teacher = "AGENT-TEACHER-"+abbrev
    username = f"swarm-{abbrev.lower()}@exam-kraft-swarm.test"
    creds = {"username":username,"password":secrets.token_urlsafe(24)}
    api("POST", "/api/v1/users/faculty/", {**creds,"email":username,"name":teacher,"department":subject,"subjects":[subject],"batch_ids":[bid for suffix,bid in batches.items() if abbrev != "BIO" or suffix.endswith("PCB")]}, action="CREATE_"+teacher)
    teacher_credentials[teacher] = creds
write_private(root / "fixtures" / "teacher_credentials.json", teacher_credentials)
for suffix, batch_id in batches.items():
    name = "QP-"+suffix
    result = api("POST", "/api/v1/question-papers/", {"name":name,"duration_minutes":55}, action="CREATE_"+name)
    assert result["question_paper"]["total_questions"] == 0
    papers[suffix] = result["id"]
    name = "EXAM-"+suffix
    result = api("POST", "/api/v1/examinations/", {"name":name,"code":name,"slug":name.lower(),"duration_minutes":55,"total_marks":40 if suffix.endswith("PCM") else 60,"question_paper_id":papers[suffix],"batch_ids":[batch_id]}, action="CREATE_"+name)
    assert result["examination"]["status"] == "DRAFT"
    assert result["examination"]["assigned_groups"] == ["BATCH-"+suffix]
    exams[suffix] = result["id"]
write_private(root / "fixtures" / "phase0_ids.json", {"organization":tenant, "batches":batches,"papers":papers,"exams":exams})
print("Phase 0 created one organization, four batches, ten students, three teachers, four empty papers, and four draft exams.")
print("Admin Zen session remains open for sequencing.", flush=True)
while True:
    command = input().strip()
    if command == "close":
        break
    if command == "verify-paper-counts":
        for suffix, paper_id in papers.items():
            result = api("GET", f"/api/v1/question-papers/{paper_id}/", expected=200, action=f"VERIFY-QP-{suffix}")
            expected_count = 10 if suffix.endswith("PCM") else 15
            observed = result.get("question_paper", result).get("total_questions")
            print(f"QP-{suffix}: {observed}/{expected_count}", flush=True)
    else:
        print("Available commands: verify-paper-counts, close", flush=True)
call("browser.close", {})
conn.close()
