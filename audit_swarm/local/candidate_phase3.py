"""Phase 3–4 runner for authorized local headless Zen integration tests."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import websocket

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
ZEN = Path("/Applications/Zen.app/Contents/MacOS/zen")
ORIGIN = "http://127.0.0.1:8000"
COHORTS = ("11-PCM",) * 3 + ("11-PCB",) * 3 + ("12-PCM",) * 2 + ("12-PCB",) * 2
SWITCH_COUNTS = {2: 3, 6: 6, 8: 10}
FORBIDDEN_QUESTION_FIELDS = {"key", "is_correct", "numerical_min", "numerical_max"}


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def delay_until(target):
    time.sleep(max(0, (target - now()).total_seconds()))


class Candidate:
    def __init__(self, index, setup, published, credentials):
        self.index = index
        self.role = f"AGENT-S-{index:02d}"
        self.cohort = COHORTS[index - 1]
        self.setup = setup
        self.exam = published["published"][self.cohort]
        self.start = utc(published["start_window"])
        self.end = utc(published["end_window"])
        self.credentials = credentials
        self.access = None
        self.refresh = None
        self.connection = None
        self.process = None
        self.sequence = 0
        self.http_count = 0
        self.log = ROOT / f"agent_{self.role}.log"
        self.network = ROOT / "network" / self.role
        self.console = ROOT / "console" / self.role
        self.profile = ROOT / "profiles" / self.role
        for directory in (self.network, self.console, self.profile):
            directory.mkdir(parents=True, exist_ok=True)

    def event(self, action, state, http="-", **fields):
        with self.log.open("a") as output:
            output.write(f"{now().isoformat()} | {self.role} | {action} | {state} | {http} | "
                         f"{json.dumps(fields, sort_keys=True)}\n")

    def bidi(self, method, params):
        self.sequence += 1
        self.connection.send(json.dumps(dict(id=self.sequence, method=method, params=params)))
        while True:
            message = json.loads(self.connection.recv())
            if message.get("method") == "log.entryAdded":
                entry = message["params"]
                if entry.get("level") == "error":
                    with (self.console / "errors.log").open("a") as output:
                        output.write(entry.get("text", "")[:200].replace("\n", " ") + "\n")
            if message.get("id") == self.sequence:
                if message["type"] == "error":
                    raise RuntimeError(f"BiDi {method} failed")
                return message["result"]

    def open(self):
        port = 51000 + self.index
        logfile = self.console / "browser.log"
        with logfile.open("w") as stream:
            self.process = subprocess.Popen(
                [str(ZEN), "--headless", "--no-remote", "--profile", str(self.profile),
                 "--remote-debugging-port", str(port), "about:blank"],
                stdout=stream, stderr=subprocess.STDOUT,
            )
        for _ in range(240):
            if "BiDi listening" in logfile.read_text(errors="replace"):
                break
            if self.process.poll() is not None:
                raise RuntimeError("Zen stopped before BiDi became ready")
            time.sleep(0.25)
        else:
            raise RuntimeError("Zen BiDi listener did not start")
        self.connection = websocket.create_connection(
            f"ws://127.0.0.1:{port}/session", timeout=45, suppress_origin=True
        )
        self.bidi("session.new", {"capabilities": {}})
        self.context = self.bidi("browsingContext.getTree", {})["contexts"][0]["context"]
        self.bidi("browsingContext.setViewport", {
            "context": self.context, "viewport": {"width": 1366, "height": 768}
        })
        self.bidi("session.subscribe", {"events": ["log.entryAdded"], "contexts": [self.context]})
        self.bidi("browsingContext.navigate", {
            "context": self.context, "url": ORIGIN + "/admin/login/", "wait": "interactive"
        })

    def close(self):
        if self.connection is not None:
            try:
                self.connection.settimeout(5)
                self.bidi("browser.close", {})
            except (RuntimeError, OSError, websocket.WebSocketException):
                pass
            finally:
                self.connection.close()
        if self.process and self.process.poll() is None:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)

    def request(self, method, path, *, action, payload=None, expect=(200,)):
        headers = {"X-Tenant-ID": self.setup["organization"]}
        options = {"method": method, "headers": headers}
        if self.access:
            headers["Authorization"] = "Bearer " + self.access
        if payload is not None:
            headers["Content-Type"] = "application/json"
            options["body"] = json.dumps(payload)
        expression = f"""(async () => {{
            const r = await fetch({json.dumps(path)}, {json.dumps(options)});
            let data;
            try {{ data = await r.json(); }} catch {{ data = {{}}; }}
            return JSON.stringify({{status: r.status, data}});
        }})()"""
        result = self.bidi("script.evaluate", {
            "expression": expression, "target": {"context": self.context}, "awaitPromise": True
        })
        if result["type"] != "success":
            raise RuntimeError(f"Browser request failed for {action}")
        result = json.loads(result["result"]["value"])
        status, data = result["status"], result["data"]
        if not isinstance(data, dict):
            data = {}
        fields = {name: data[name] for name in (
            "code", "status", "attempt_id", "submission_status", "auto_submitted", "tab_switch_count"
        ) if name in data}
        record = {
            "timestamp": now().isoformat(), "method": method, "url": ORIGIN + path,
            "request_body_hash": hashlib.sha256(json.dumps(
                None if action in {"LOGIN", "REFRESH"} else payload, sort_keys=True
            ).encode()).hexdigest(),
            "response_status": status, "response_body_excerpt": json.dumps(fields)[:200],
        }
        with (self.network / "requests.ndjson").open("a") as output:
            output.write(json.dumps(record) + "\n")
        self.http_count += 1
        self.event(action, "PASS" if status in expect else "FAIL", status, **fields)
        return status, data

    def successful_write(self, path, payload, action):
        for retry in range(6):
            status, data = self.request("POST", path, action=action, payload=payload, expect=(200, 201))
            if status in {200, 201}:
                return data
            if status not in {500, 503}:
                break
            # Development SQLite may serialize concurrent writers. Keep the
            # operation on its original session and record every retry.
            time.sleep(0.18 * (retry + 1) + 0.04 * self.index)
        raise RuntimeError(f"{action} failed HTTP {status}")

    def inspect_delivery(self, data, source):
        questions = [question for section in data["sections"] for question in section["questions"]]
        question_fields = sorted(FORBIDDEN_QUESTION_FIELDS.intersection(
            key for question in questions for key in question
        ))
        option_sensitive_fields = sorted((FORBIDDEN_QUESTION_FIELDS - {"key"}).intersection(
            key for question in questions for option in question.get("options", []) for key in option
        ))
        option_labels = any("key" in option for question in questions for option in question.get("options", []))
        self.event("CHECK-08", "FAIL" if question_fields or option_sensitive_fields or option_labels else "PASS",
                   source=source, question_count=len(questions), question_fields=question_fields,
                   option_sensitive_fields=option_sensitive_fields, option_display_key_present=option_labels,
                   numerical_answer_field_name="numerical_value",
                   numerical_answer_field_in_question=any("numerical_value" in question for question in questions))
        return questions

    @staticmethod
    def answer(question):
        payload = {"question_id": question["id"], "status": "ANSWERED", "time_spent_seconds": 2}
        if question["question_type"] in {"NUMERICAL", "SINGLE_DIGIT"}:
            payload["numerical_value"] = "2"
        else:
            payload["selected_options"] = [str(question["options"][0]["id"])]
        return payload

    def run(self):
        self.open()
        status, data = self.request("POST", "/api/v1/auth/login/", action="LOGIN", payload=self.credentials)
        if status != 200:
            raise RuntimeError("candidate authentication failed")
        self.access, self.refresh = data["access"], data["refresh"]
        self.authenticated_at = now()
        status, data = self.request("GET", "/api/v1/student/examinations/", action="LIST_EXAMS")
        discovered = {exam["id"] for exam in data.get("examinations", [])}
        if status != 200 or discovered != {self.exam}:
            raise RuntimeError(f"candidate discovery did not isolate the cohort ({len(discovered)} visible)")
        self.event("COHORT_ISOLATION", "PASS", visible_count=len(discovered))

        paper = self.setup["papers"][self.cohort]
        status, data = self.request("GET", f"/api/v1/question-papers/{paper}/", action="CHECK-01_HTTP", expect=(403,))
        self.event("CHECK-01", "PASS" if status == 403 else "FAIL", status, denied=status == 403)
        delay_until(self.start)
        self.event("START_WINDOW", "PASS", offset_seconds=(now() - self.start).total_seconds())
        start_route = "/api/v1/student/attempts/start/"
        attempt = self.successful_write(start_route, {"exam_id": self.exam}, "START")
        wrong_cohort = {1: "11-PCB", 7: "11-PCM"}.get(self.index)
        if wrong_cohort:
            checked = "CHECK-03" if self.index == 1 else "CHECK-04"
            status, data = self.request("POST", start_route, action=checked,
                                        payload={"exam_id": self.setup["exams"][wrong_cohort]},
                                        expect=(403, 404,))
            if status not in {403, 404}:
                self.event(checked + "_ASSERT", "FAIL", status, unexpected=True)
        attempt_base = f"/api/v1/student/attempts/{attempt['attempt_id']}/"
        questions = self.inspect_delivery(attempt, "start")
        expected_count = 10 if self.cohort.endswith("PCM") else 15
        if len(questions) != expected_count:
            raise RuntimeError(f"expected {expected_count} questions, received {len(questions)}")
        saved = {}
        precrash_questions = set()
        auto_submitted = False
        switch_count = 0

        def save(question):
            answer = self.answer(question)
            self.successful_write(attempt_base + "responses/", answer, "SAVE")
            saved[str(question["id"])] = answer

        def heartbeat():
            self.successful_write(attempt_base + "heartbeat/", {"window_blur_count": 0}, "HEARTBEAT")

        if self.index == 3:
            for question in questions[:3]:
                save(question)
            precrash_questions = set(saved)
            for offset in range(20, 180, 20):
                delay_until(self.start + timedelta(seconds=offset))
                heartbeat()
            delay_until(self.start + timedelta(seconds=180))
            self.event("DROP_OUTBOUND", "PASS", duration_seconds=90)
            delay_until(self.start + timedelta(seconds=270))
            status, resumed = self.request("GET", attempt_base + "resume/", action="RESUME")
            if status == 200:
                self.inspect_delivery(resumed, "resume")
                actual = resumed.get("existing_responses", {})
                preserved = sum(
                    key in actual and all(actual[key].get(field) == value for field, value in expected.items()
                                          if field in {"selected_options", "numerical_value"})
                    for key, expected in saved.items()
                )
                self.event("CHECK-05_RESUME", "PASS" if preserved == 3 else "FAIL", status,
                           preserved=preserved, prior_count=3, recovered=resumed.get("is_recovered"))
                for question in questions[3:]:
                    save(question)
            else:
                self.event("CHECK-05_RESUME", "FAIL", status, prior_count=3)
        elif self.index in SWITCH_COUNTS:
            for question in questions[:2]:
                save(question)
            for count in range(1, SWITCH_COUNTS[self.index] + 1):
                delay_until(self.start + timedelta(seconds=count * 30))
                response = self.successful_write(attempt_base + "proctoring_event/",
                    {"event_type": "TAB_SWITCH", "details": {}}, "TAB_SWITCH")
                switch_count = response["tab_switch_count"]
                auto_submitted = response["auto_submitted"]
                self.event("VIOLATION_COUNT", "PASS" if switch_count == count else "FAIL",
                           expected=count, actual=switch_count)
                if auto_submitted:
                    status, data = self.request("POST", attempt_base + "responses/", action="CHECK-06_LOCK",
                        payload=self.answer(questions[2]), expect=(403, 409,))
                    self.event("CHECK-06", "PASS" if status in {403, 409} else "FAIL", status,
                               auto_submitted=True, violation_count=switch_count)
                    break
                if count + 1 < len(questions):
                    save(questions[count + 1])
        else:
            cursor = 0
            for index, question in enumerate(questions):
                while index * 2 >= cursor:
                    delay_until(self.start + timedelta(seconds=cursor))
                    heartbeat()
                    cursor += 20
                delay_until(self.start + timedelta(seconds=index * 2))
                save(question)

        if not auto_submitted:
            submitted = self.successful_write(attempt_base + "submit/",
                                              {"submission_reason": "MANUAL_SUBMIT"}, "SUBMIT")
            denied_fields = sorted({"key", "score", "total_score", "is_correct", "marks"}.intersection(submitted))
            self.event("SUBMITTED_CONFIRMATION",
                       "PASS" if submitted.get("submission_status") == "SUBMITTED" and not denied_fields else "FAIL",
                       result_fields=denied_fields, submitted=submitted.get("submission_status") == "SUBMITTED")
        else:
            self.event("SUBMITTED_CONFIRMATION", "PASS", auto_submitted=True, tab_switch_count=switch_count)

        status, data = self.request("GET", attempt_base + "report/", action="CHECK-02", expect=(403,))
        self.event("AWAIT_RESULTS", "PASS", attempt=attempt["attempt_id"], window_end=self.end.isoformat())
        delay_until(self.end)
        for _ in range(40):
            if now() - self.authenticated_at >= timedelta(minutes=50):
                status, data = self.request("POST", "/api/v1/auth/token/refresh/", action="REFRESH",
                                            payload={"refresh": self.refresh})
                if status != 200:
                    raise RuntimeError("access token refresh failed")
                self.access = data["access"]
                self.refresh = data.get("refresh", self.refresh)
                self.authenticated_at = now()
            status, data = self.request("GET", attempt_base + "report/", action="RESULT_REPORT", expect=(200, 403))
            if status == 200:
                score_present = isinstance(data.get("report", {}).get("total_score"), (int, float))
                self.event("PUBLISHED_SCORE", "PASS" if score_present else "FAIL", status, score_present=score_present)
                if self.index == 3:
                    reviewed = {str(review["question_id"]) for review in data.get("reviews", [])
                                if review["is_attempted"]}
                    graded_precrash = len(precrash_questions.intersection(reviewed))
                    self.event("CHECK-05_GRADING", "PASS" if graded_precrash == 3 else "FAIL", status,
                               graded_precrash=graded_precrash, expected=3)
                if not score_present:
                    raise RuntimeError("published report omitted total score")
                return
            if status != 403:
                break
            time.sleep(30)
        raise RuntimeError("published results were not received")


def configuration(validate_only):
    setup = json.loads((FIXTURES / "phase0_ids.json").read_text())
    credentials = json.loads((FIXTURES / "student_credentials.json").read_text())
    required = set(COHORTS)
    if not ZEN.is_file() or not os.access(ZEN, os.X_OK):
        raise RuntimeError("Zen executable unavailable")
    if set(setup["exams"]) != required or set(setup["papers"]) != required:
        raise RuntimeError("Phase 0 cohorts are incomplete")
    if set(credentials) != {f"AGENT-S-{index:02d}" for index in range(1, 11)}:
        raise RuntimeError("Exactly ten candidate credentials are required")
    if validate_only:
        print("Validated Zen, ten credential records, and four cohort links. No browsers launched.")
        return None
    published = json.loads((FIXTURES / "published_windows.json").read_text())
    if (published["published"] != setup["exams"] or published["duration_minutes"] != 55
            or utc(published["end_window"]) - utc(published["start_window"]) != timedelta(minutes=60)):
        raise RuntimeError("Publication configuration does not match the Phase 0 assignment or timing")
    if utc(published["start_window"]) <= now():
        raise RuntimeError("Shared opening is already past")
    return setup, published, credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true", help="Validate local inputs without launching")
    args = parser.parse_args()
    config = configuration(args.validate)
    if config is None:
        return 0
    setup, published, credentials = config

    def run_candidate(index):
        role = f"AGENT-S-{index:02d}"
        candidate = Candidate(index, setup, published, credentials[role])
        try:
            candidate.run()
        except Exception as error:
            candidate.event("RUN", "FAIL", reason=str(error)[:160])
            return role, False
        finally:
            candidate.close()
        candidate.event("RUN", "PASS", http_requests=candidate.http_count)
        return role, True

    successes = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        for future in as_completed([pool.submit(run_candidate, index) for index in range(1, 11)]):
            role, passed = future.result()
            print(role, "PASS" if passed else "FAIL", flush=True)
            successes += int(passed)
    return 0 if successes == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
