import json
import sys
import time
from pathlib import Path

import websocket

connection = websocket.create_connection(sys.argv[1] + "/session", timeout=50, suppress_origin=True)
sequence = 0
responses = []

def call(method, params):
    global sequence
    sequence += 1
    connection.send(json.dumps({"id": sequence, "method": method, "params": params}))
    while True:
        message = json.loads(connection.recv())
        if message.get("method") == "network.responseCompleted":
            response = message["params"]["response"]
            if "/api/" in response["url"]:
                responses.append((response["status"], response["url"]))
        if message.get("id") == sequence:
            if message["type"] == "error":
                raise RuntimeError(message["message"])
            return message["result"]

def evaluate(expression):
    result = call("script.evaluate", {
        "expression": expression, "target": {"context": context}, "awaitPromise": True
    })
    if result["type"] != "success":
        raise RuntimeError("Browser script failed")
    return result["result"].get("value")

def wait_for(expression):
    for _ in range(160):
        value = evaluate(expression)
        if value:
            return value
        time.sleep(0.25)
    raise RuntimeError("Expected UI state did not appear")

try:
    call("session.new", {"capabilities": {}})
    context = call("browsingContext.getTree", {})["contexts"][0]["context"]
    call("session.subscribe", {"events": ["network.responseCompleted"], "contexts": [context]})
    call("browsingContext.navigate", {"context": context, "url": "http://127.0.0.1:5173/login", "wait": "interactive"})
    wait_for("Boolean(document.querySelector('input[type=password]'))")
    password = Path(__file__).with_name("demo-password").read_text().strip()
    evaluate("""(() => {
        const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        for (const [selector, value] of [
            ['input[type=text]', 'student@ezexam.local'],
            ['input[type=password]', """ + json.dumps(password) + """]
        ]) {
            const input = document.querySelector(selector);
            set.call(input, value);
            input.dispatchEvent(new Event('input', {bubbles: true}));
        }
    })()""")
    evaluate("document.querySelector('button[type=submit]').click()")
    wait_for("location.pathname === '/student'")
    wait_for("document.body.innerText.includes('Exam')")
    print("PASS: seeded candidate signed in and reached a dashboard displaying exam content.")
    for status, url in responses:
        print(status, url)
finally:
    try:
        call("browser.close", {})
    finally:
        connection.close()
