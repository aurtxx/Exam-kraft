import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import websocket

root = Path('audit_swarm')
role = 'AGENT-TEACHER-PHY'
base = 'http://127.0.0.1:8000'
setup = json.loads((root / 'fixtures/phase0_ids.json').read_text())
credential = json.loads((root / 'fixtures/teacher_credentials.json').read_text())[role]
conn = websocket.create_connection('ws://127.0.0.1:50961/session', timeout=45, suppress_origin=True)
sequence = 0
token = None

def call(method, params):
    global sequence
    sequence += 1
    conn.send(json.dumps(dict(id=sequence, method=method, params=params)))
    while True:
        message = json.loads(conn.recv())
        if message.get('method') == 'log.entryAdded':
            entry = message['params']
            if entry.get('level') == 'error':
                log_path = root / 'console' / role / 'errors.log'
                with log_path.open('a') as out:
                    out.write(f"{entry.get('text', '')[:200]}\n")
        if message.get('id') == sequence:
            if message['type'] == 'error':
                raise RuntimeError(method)
            return message['result']

def log(action, verdict, status, detail):
    stamp = datetime.now(timezone.utc).isoformat()
    with (root / f'agent_{role}.log').open('a') as out:
        out.write(f'{stamp} | {role} | {action} | {verdict} | {status} | {detail}\n')

def request(method, route, body=None, *, fixture=None, action, expected):
    headers = {'X-Tenant-ID': setup['organization']}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    options = {'method': method, 'headers': headers}
    if fixture:
        raw = (root / 'fixtures' / fixture).read_bytes()
        payload = base64.b64encode(raw).decode()
        payload_javascript = f"""const data = new FormData();
        const bytes = Uint8Array.from(atob({json.dumps(payload)}), c => c.charCodeAt(0));
        data.append('file', new Blob([bytes], {{type:'image/png'}}), {json.dumps(fixture)});
        data.append('section_name', 'Physics');
        opts.body = data;"""
        digest = hashlib.sha256(raw).hexdigest()
    else:
        if body is not None:
            headers['Content-Type'] = 'application/json'
            options['body'] = json.dumps(body)
        payload_javascript = ''
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    expression = f"""(async () => {{
        const opts = {json.dumps(options)};
        {payload_javascript}
        const response = await fetch({json.dumps(route)}, opts);
        let payload;
        try {{ payload = await response.json(); }} catch {{ payload = {{}}; }}
        return JSON.stringify({{status: response.status, payload}});
    }})()"""
    result = call('script.evaluate', dict(expression=expression, target={'context': context}, awaitPromise=True))
    if result['type'] != 'success':
        raise RuntimeError('Browser evaluation failed: ' + result.get('exceptionDetails', {}).get('text', 'unknown'))
    result = json.loads(result['result']['value'])
    status, payload = result['status'], result['payload']
    summary = {key: payload[key] for key in ('id','code','message','status') if key in payload}
    excerpt = '' if action == 'LOGIN' else json.dumps(summary)
    stamp = datetime.now(timezone.utc).isoformat()
    with (root / 'network' / role / 'requests.ndjson').open('a') as out:
        out.write(json.dumps(dict(timestamp=stamp,method=method,url=base + route,request_body_hash=digest,
            response_status=status,response_body_excerpt=excerpt[:200])) + '\n')
    log(action, 'PASS' if status in expected else 'FAIL', status, excerpt)
    return status, payload

def mcq(number, stem, options):
    return dict(question_number=number, content_text='Physics audit: ' + stem,
        section_name='Physics', question_type='MCQ_SINGLE', positive_marks=4,
        options=[dict(text=text, is_correct=index == 0) for index, text in enumerate(options)])

def numerical(number, stem, answer):
    return dict(question_number=number, content_text='Physics audit: ' + stem,
        section_name='Physics', question_type='NUMERICAL', positive_marks=4, key=str(answer),
        numerical_min=answer - 0.05, numerical_max=answer + 0.05)

questions = [
    mcq(1, 'Which SI unit measures force?', ['newton','joule','watt','pascal']),
    numerical(2, 'A 2 kg mass accelerates at 3 m/s². Give the net force in newtons.', 6),
    mcq(3, 'Which quantity is a vector?', ['velocity','speed','time','mass']),
    numerical(4, 'A runner covers 15 m in 3 s at constant speed. Give the speed in m/s.', 5),
    mcq(5, 'Which SI unit measures electric current?', ['ampere','volt','ohm','coulomb']),
]
try:
    call('session.new', {'capabilities': {}})
    context = call('browsingContext.getTree', {})['contexts'][0]['context']
    call('browsingContext.setViewport', {'context': context, 'viewport': {'width': 1366, 'height': 768}})
    call('session.subscribe', {'events': ['log.entryAdded'], 'contexts': [context]})
    call('browsingContext.navigate', {'context': context, 'url': base + '/admin/login/', 'wait': 'complete'})
    status, response = request('POST','/api/v1/auth/login/',credential,action='LOGIN',expected=(200,))
    if status != 200:
        raise RuntimeError('Teacher login failed')
    token = response['access']
    for paper, uid in setup['papers'].items():
        route = f'/api/v1/question-papers/{uid}/questions/'
        for index, question in enumerate(questions):
            action = f'{paper}_{("A","A","B_FALLBACK","B_FALLBACK","C_FALLBACK")[index]}_{index + 1}'
            if index in (2, 3):
                status, result = request('POST',route,fixture='sample_question.png',action=f'{paper}_B_PNG_{index + 1}',expected=(400,415,))
                if status not in (400,415):
                    raise RuntimeError('Unexpected image upload response')
            if index == 4:
                log(f'{paper}_C_XLSX', 'UNSUPPORTED', '-', 'TEACHER-FINDING-002: Excel answer key import not implemented')
            for retry in range(4):
                status, result = request('POST',route,question,action=action,expected=(201,))
                if status == 201:
                    break
                if status != 500:
                    raise RuntimeError(f'{action} failed HTTP {status}')
                time.sleep(0.25 * (retry + 1))
                _, list_result = request('GET',route,action=f'{action}_RECHECK',expected=(200,))
                if any(q.get('content_text') == question['content_text'] for q in list_result.get('questions', [])):
                    break
            else:
                raise RuntimeError(f'{action} exhausted retries')
        status, result = request('GET',route,action=f'{paper}_VERIFY',expected=(200,))
        own_questions = [q for q in result.get('questions',[]) if q.get('content_text','').startswith('Physics audit: ')]
        if status != 200 or sorted(q['content_text'] for q in own_questions) != sorted(q['content_text'] for q in questions):
            raise RuntimeError(f'{paper} has {len(own_questions)} Physics questions')
        log(f'{paper}_COUNT', 'PASS', status, 'Five expected Physics questions present')
finally:
    try:
        call('browser.close', {})
    finally:
        conn.close()
