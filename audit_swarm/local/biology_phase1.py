import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import websocket

root = Path("audit_swarm")
agent = "AGENT-TEACHER-BIO"
credentials = json.loads((root / "fixtures/teacher_credentials.json").read_text())[agent]
ids = json.loads((root / "fixtures/phase0_ids.json").read_text())
for folder in ("network", "console"):
    (root / folder / agent).mkdir(parents=True, exist_ok=True)
log_path = root / f"agent_{agent}.log"
network_path = root / "network" / agent / "requests.ndjson"
console_path = root / "console" / agent / "errors.log"
console_path.touch()
conn = websocket.create_connection(sys.argv[1] + "/session", timeout=45, suppress_origin=True)
sequence = 0

def now():
    return datetime.now(timezone.utc).isoformat()

def log(action, outcome, status, note):
    with log_path.open("a") as file:
        print(now(), agent, action, outcome, status, note, sep=" | ", file=file)

def call(method, params):
    global sequence
    sequence += 1
    conn.send(json.dumps(dict(id=sequence, method=method, params=params)))
    while True:
        message = json.loads(conn.recv())
        if message.get("method") == "log.entryAdded":
            record = message["params"]
            if record.get("level") == "error":
                with console_path.open("a") as file:
                    print(record.get("text", ""), file=file)
        if message.get("id") == sequence:
            if message["type"] == "error":
                raise RuntimeError(message.get("message"))
            return message["result"]

def evaluate(expression):
    result = call("script.evaluate", {"expression": expression, "target": {"context": context}, "awaitPromise": True, "serializationOptions": {"maxObjectDepth": 1}})
    if result["type"] != "success":
        raise RuntimeError("Page script failed: " + result.get("exceptionDetails", {}).get("text", ""))
    return result["result"]["value"]

def api(method, path, payload=None, fixture=None):
    opts = dict(method=method, headers={"X-Tenant-ID": ids["organization"]})
    if token:
        opts["headers"]["Authorization"] = "Bearer " + token
    if fixture is None:
        raw = json.dumps(payload).encode() if payload is not None else b""
        if payload is not None:
            opts["headers"]["Content-Type"] = "application/json"
            opts["body"] = raw.decode()
        attach = ""
    else:
        raw = fixture.read_bytes()
        mime = "image/png" if fixture.suffix == ".png" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        form = json.dumps(dict(fields=payload, data=base64.b64encode(raw).decode(), name=fixture.name, mime=mime))
        attach = f"""
        const spec = {form}, form = new FormData();
        for (const [name, value] of Object.entries(spec.fields)) form.set(name, value);
        const file = new File([Uint8Array.from(atob(spec.data), n => n.charCodeAt(0))],spec.name,{{type:spec.mime}});
        const input = document.createElement('input'); input.type = 'file';
        const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files;
        form.set('file', input.files[0]);
        opts.body = form;
        """
    expression = f"""(async () => {{
        const opts = {json.dumps(opts)};
        {attach}
        const response = await fetch({json.dumps(path)},opts);
        const type = response.headers.get('content-type') || '';
        const payload = type.includes('application/json') ? await response.json() : {{}};
        const allowed = ['status','id','code','message','detail'];
        return JSON.stringify({{status:response.status,data:payload, excerpt:Object.fromEntries(
            Object.entries(payload).filter(([key])=>allowed.includes(key))) }});
    }})()"""
    result = json.loads(evaluate(expression))
    entry = dict(timestamp=now(), method=method, url=path, request_body_hash=hashlib.sha256(raw).hexdigest(), response_status=result["status"], response_body_excerpt="" if path.endswith("/auth/login/") else json.dumps(result["excerpt"], ensure_ascii=True)[:200])
    with network_path.open("a") as file:
        print(json.dumps(entry), file=file)
    return result["status"], result["data"], entry["response_body_excerpt"]

def mcq(stem, correct, wrong):
    return dict(question_type="MCQ_SINGLE", content_text=stem, section="Biology", positive_marks=4, options=[dict(text=value, is_correct=index==0) for index, value in enumerate([correct, *wrong])])

def numerical(stem, answer):
    return dict(question_type="NUMERICAL", content_text=stem, section="Biology", key=str(answer), numerical_min=answer, numerical_max=answer, positive_marks=4)

sets = {
    "11-PCB": [
        mcq("Which organelle is the main site of aerobic ATP production?", "Mitochondrion", ["Nucleolus", "Golgi apparatus", "Lysosome"]),
        numerical("How many chambers are in a typical adult human heart?", 4),
        mcq("What process moves water through a selectively permeable membrane?", "Osmosis", ["Translation", "Glycolysis", "Transcription"]),
        numerical("How many oxygen atoms are in one molecule of carbon dioxide?", 2),
        mcq("Which plant tissue transports water upward?", "Xylem", ["Phloem", "Epidermis", "Pith"]),
    ],
    "12-PCB": [
        mcq("What is the term for the observable traits of an organism?", "Phenotype", ["Genotype", "Allele", "Locus"]),
        numerical("How many chromosomes are present in a typical human egg cell?", 23),
        mcq("What process produces RNA from a DNA template?", "Transcription", ["Translation", "Replication", "Fermentation"]),
        numerical("How many nucleotides make up one codon?", 3),
        mcq("What molecules recognize specific antigens in acquired immunity?", "Antibodies", ["Triglycerides", "Starch", "Cellulose"]),
    ],
}

token = ""
try:
    call("session.new", {"capabilities": {}})
    context = call("browsingContext.getTree", {})["contexts"][0]["context"]
    call("session.subscribe", {"events": ["log.entryAdded"], "contexts": [context]})
    call("browsingContext.navigate", {"context": context, "url": "http://127.0.0.1:5173/login", "wait":"interactive"})
    status, data, _ = api("POST","/api/v1/auth/login/",credentials)
    log("LOGIN", "PASS" if status == 200 else "FAIL", status, "Biology teacher")
    if status != 200:
        raise RuntimeError("Teacher authentication failed")
    token = data["access"]
    findings = []
    for cohort, questions in sets.items():
        paper_id = ids["papers"].get(cohort) or ids["papers"][f"QP-{cohort}"]
        path = f"/api/v1/question-papers/{paper_id}/questions/"
        status, data, _ = api("GET", path)
        if status != 200:
            raise RuntimeError(f"Read paper returned {status}")
        previous = {question["content_text"] for question in data["questions"]}
        for index, question in enumerate(questions):
            if question["content_text"] in previous:
                continue
            if index in (2, 3):
                fixture = root / "fixtures/sample_question.png"
                status, _, excerpt = api("POST", path, {"content_text": fixture.name, "question_text":fixture.name}, fixture)
                log(f"PNG_{cohort}_{index}", "UNSUPPORTED" if status == 400 else "OBSERVED", status, excerpt)
                findings.append(f"{cohort} PNG attempt {index-1} returned HTTP {status} with {excerpt}.")
                if status != 400:
                    raise RuntimeError(f"Unexpected PNG response {status}")
            if index == 4:
                findings.append(f"{cohort} XLSX import unavailable. The configured question authoring routes have no Excel answer-key endpoint.")
                log(f"EXCEL_{cohort}", "UNSUPPORTED", "N/A", "No routed Excel answer-key import endpoint")
            for attempt in range(5):
                status, _, excerpt = api("POST", path, question)
                log(f"AUTHOR_{cohort}_{index+1}", "PASS" if status == 201 else "FAIL", status, excerpt)
                if status != 500:
                    break
                time.sleep(0.4 + attempt * 0.3)
            if status != 201:
                raise RuntimeError(f"Question authoring returned {status}")
        status, data, _ = api("GET", path)
        authored = {question["content_text"] for question in data.get("questions", [])}
        expected = {question["content_text"] for question in questions}
        success = status == 200 and expected <= authored
        log(f"VERIFY_{cohort}", "PASS" if success else "FAIL", status, f"{len(expected & authored)} of 5 Biology questions")
        if not success:
            raise RuntimeError("Biology count mismatch")
    (root / "local/biology_upload_findings.md").write_text("# Biology upload findings\n\n" + "\n".join(f"- {item}" for item in findings) + "\n")
    log("AUTHORIZATION_HANDOFF", "PENDING", "N/A", "Student role will perform its own authorization verification")
finally:
    try:
        call("browser.close", {})
    finally:
        conn.close()
