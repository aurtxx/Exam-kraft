"""Exercise a fresh demo exam through the live HTTP API."""
import argparse
import asyncio
import os
import statistics
from time import perf_counter
from uuid import UUID

import httpx


async def request(client, method, path, headers=None, payload=None):
    response = await client.request(method, f"/api/v1/{path}", headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    if data.get("status", "SUCCESS") != "SUCCESS":
        raise ValueError(f"{path} returned {data.get('status')}")
    return data


async def benchmark(args, password):
    limits = httpx.Limits(max_connections=args.candidates, max_keepalive_connections=args.candidates)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60, limits=limits) as client:
        candidates = range(1, args.candidates + 1)

        async def phase(name, action):
            async def timed(number):
                started = perf_counter()
                try:
                    return await action(number), perf_counter() - started
                except Exception as exc:
                    return exc, perf_counter() - started

            results = await asyncio.gather(*(timed(number) for number in candidates))
            successes = [elapsed for result, elapsed in results if not isinstance(result, Exception)]
            errors = [(number, result) for number, (result, _) in zip(candidates, results)
                      if isinstance(result, Exception)]
            print(f"{name}: {len(successes)}/{args.candidates} succeeded", end="")
            if successes:
                p95 = statistics.quantiles(successes, n=20, method="inclusive")[18] if len(successes) > 1 else successes[0]
                print(f" | p50 {statistics.median(successes):.3f}s | p95 {p95:.3f}s", end="")
            print()
            for number, error in errors[:5]:
                print(f"  Candidate {number:03d}: {error}")
            if errors:
                raise SystemExit(1)
            return dict(zip(candidates, (result for result, _ in results)))

        async def login(number):
            data = await request(client, "POST", "auth/login/", payload={
                "username": f"student{number:03d}@demo-apex.ezexam.example", "password": password,
            })
            return {"Authorization": f"Bearer {data['access']}"}

        headers = await phase("Login", login)

        async def start(number):
            data = await request(client, "POST", "attempts/start/", headers[number], {"exam_id": args.exam_id})
            if data["remaining_seconds"] <= 0 or data["is_recovered"]:
                raise ValueError("Expected a fresh attempt with time remaining")
            return data

        attempts = await phase("Start", start)
        if len({attempt["attempt_id"] for attempt in attempts.values()}) != args.candidates:
            raise SystemExit("Expected one distinct attempt per candidate")

        async def attempt_request(number, action, method="POST", payload=None):
            attempt_id = attempts[number]["attempt_id"]
            return await request(client, method, f"attempts/{attempt_id}/{action}/", headers[number], payload)

        async def heartbeat(number):
            data = await attempt_request(number, "heartbeat", payload={})
            if not 0 < data["remaining_seconds"] <= attempts[number]["remaining_seconds"] or data["is_terminated"]:
                raise ValueError("Invalid heartbeat timer")

        await phase("Heartbeat", heartbeat)

        async def save(number):
            saved = {}
            for section in attempts[number]["sections"]:
                for question in section["questions"][:3]:
                    choices = question["options"]
                    answer = {"selected_options": [option["key"] for option in choices[:2 if question["question_type"] == "MCQ_MULTI" else 1]]} if choices else {"numerical_value": "9"}
                    question_id = question["id"]
                    response = await attempt_request(number, "save_response", payload={
                        "question_id": question_id, "time_spent_seconds": 3, **answer,
                    })
                    if response["question_id"] != question_id or response["remaining_seconds"] <= 0:
                        raise ValueError("Invalid save acknowledgement")
                    saved[question_id] = answer
            if not saved:
                raise ValueError("No questions delivered")
            return saved

        answers = await phase("Save responses", save)

        async def verify_saved(number):
            data = await attempt_request(number, "resume", method="GET")
            for question_id, answer in answers[number].items():
                saved = data["existing_responses"][question_id]
                if saved["time_spent_seconds"] != 3 or any(saved[key] != value for key, value in answer.items()):
                    raise ValueError(f"Response mismatch for {question_id}")

        await phase("Verify persisted responses", verify_saved)

        async def submit(number):
            data = await attempt_request(number, "submit", payload={})
            if data["submission_status"] != "SUBMITTED" or data["attempt_id"] != attempts[number]["attempt_id"]:
                raise ValueError("Invalid submission acknowledgement")
            return data

        submissions = await phase("Submit", submit)

        async def verify_submit(number):
            data = await submit(number)
            if data.get("code") != "ALREADY_SUBMITTED" or data["submitted_at"] != submissions[number]["submitted_at"]:
                raise ValueError("Submission was not recorded idempotently")

        await phase("Verify recorded submissions", verify_submit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--exam-id", required=True, type=lambda value: str(UUID(value)))
    parser.add_argument("--candidates", type=int, default=100, choices=range(1, 111), metavar="1–110")
    args = parser.parse_args()
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        parser.error("Set DEMO_PASSWORD to the password used for seeding.")
    asyncio.run(benchmark(args, password))
