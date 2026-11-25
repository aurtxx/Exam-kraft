# EZExam

Multi-tenant examination platform with a React candidate and staff interface, a Django REST API, and PostgreSQL for deployment.

## Local development

Use Python 3.12 and Node.js 20. From the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt pytest httpx
python backend/manage.py migrate
export DEMO_PASSWORD='replace-with-a-local-demo-password'
python backend/manage.py seed_demo_data
python backend/manage.py runserver
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open the frontend at http://localhost:5173 and Django admin at http://localhost:8000/admin/. Local development uses SQLite by default. For PostgreSQL, set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and optionally `DB_PORT` (5432).

### Demo data

Seed only a development or disposable staging database. The command creates Apex Academy and Summit Academy, their JEE 2027 batches and centers, 125 enrolled candidates, and a 12-question paper per tenant spanning Mathematics, Physics, and Chemistry. Each tenant gets an open published exam and a future scheduled exam. The command prints the published exam UUIDs.

| Role | Apex demo username |
| --- | --- |
| Platform superadmin | `superadmin@demo.ezexam.example` |
| Organization administrator | `admin@demo-apex.ezexam.example` |
| Faculty | `faculty@demo-apex.ezexam.example` |
| Candidate | `student001@demo-apex.ezexam.example` through `student110@demo-apex.ezexam.example` |

Every newly created account uses `DEMO_PASSWORD` (minimum 12 characters). Rerunning the command keeps existing passwords and attempts and refreshes the demo exam windows. Use a unique `--exam-code` to create a fresh exam for another benchmark.

## Docker deployment

Install Docker with the Compose v2 plugin. Set `SECRET_KEY` and `POSTGRES_PASSWORD` to independent random secrets in your deployment environment or in an untracked root `.env` file. For example, generate each value with `openssl rand -hex 32`. Compose also accepts these settings:

| Setting | Default | Purpose |
| --- | --- | --- |
| `PUBLIC_HOST` | `localhost` | Additional allowed Django hostname |
| `HTTP_PORT` | `8080` | Loopback listener for the Nginx gateway |
| `HTTPS_ENABLED` | `0` | Set to `1` to enable secure Django session and CSRF cookies behind TLS |
| `CSRF_TRUSTED_ORIGINS` | Empty | Comma-separated trusted origins with schemes, if needed |

```sh
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps -a
curl -fsS http://localhost:8080/healthz/
curl -fsS http://localhost:8080/readyz/
docker compose logs backend worker migrate
```

The migration service applies database migrations before Gunicorn starts. The backend image collects Django static files at build time. Nginx forwards API, admin, static, and probe requests to Django and serves the React SPA through the frontend container. The Celery worker uses Redis as its broker. PostgreSQL and Redis use persistent volumes and internal network ports.

For a public deployment, terminate TLS at a reverse proxy on the host. Forward the public Host header and overwrite `X-Forwarded-Proto` with the original scheme at that trusted proxy. Set `PUBLIC_HOST` and `HTTPS_ENABLED=1`. Back up PostgreSQL before applying updates. Existing PostgreSQL volumes retain their original database users and credentials, so migrate or explicitly provision the `ezexam` role before switching a volume initialized by the previous Compose configuration.

`/healthz/` checks Django liveness. `/readyz/` checks database connectivity and, in deployment mode, Redis connectivity.

## Tests and candidate benchmark

Run the Django suite and the contract suite from the root. The contract suite uses a mock HTTP transport by default.

```sh
python backend/manage.py test backend/tests apps
python -m pytest
npm --prefix frontend run build
```

Use a disposable PostgreSQL deployment for the concurrent HTTP benchmark. Export `DEMO_PASSWORD`, seed a new exam, and copy the printed `demo-apex` exam ID.

```sh
docker compose exec -e DEMO_PASSWORD backend python manage.py seed_demo_data --exam-code M5-RUN-01
python tests/benchmark_100_candidates.py --base-url http://localhost:8080 --exam-id EXAM_UUID
```

The benchmark defaults to 100 candidates and supports up to 110 with `--candidates`. It issues concurrent login, start, heartbeat, response save, recovery, and submission requests in successive phases. It verifies distinct attempts, positive server timers, persisted responses and time spent, and idempotent submission acknowledgements. It reports phase success counts and p50/p95 elapsed times, and exits nonzero on failures. Use a fresh exam code after a failed or completed run.

## API reference

API routes use the `/api/v1/` prefix and trailing slashes. Send JSON request bodies and include `Authorization: Bearer <access>` on authenticated routes. Login accepts `username` and `password` and returns access and refresh tokens. Tenant context comes from the JWT, tenant header (`X-Tenant-ID`), or host mapping.

| Method | Path under `/api/v1/` | Purpose |
| --- | --- | --- |
| POST | `auth/login/`, `auth/token/refresh/`, `auth/logout/` | Issue, refresh, or revoke tokens |
| GET | `auth/me/`, `organizations/current/` | Current account and tenant |
| GET, POST | `organizations/batches/`, `organizations/centers/` | Manage tenant cohorts and centers |
| GET, POST | `question-papers/` | List or author question papers |
| GET, POST | `examinations/` | List or create examinations |
| POST | `examinations/<id>/assign-candidates/`, `examinations/<id>/publish/` | Assign or publish an exam |
| POST | `attempts/start/` | Start with `{"exam_id":"<uuid>"}` |
| POST | `attempts/<id>/heartbeat/` | Read server time and remaining seconds |
| POST | `attempts/<id>/save_response/` | Send `question_id`, `time_spent_seconds`, and `selected_options` or `numerical_value` |
| GET | `attempts/<id>/resume/` | Recover questions, saved responses, and timer |
| POST | `attempts/<id>/submit/` | Submit using an empty JSON object for manual submission |
| GET | `attempts/<id>/report/`, `analytics/results/` | Read attempt reports and results |
| POST | `analytics/examinations/<id>/evaluate/`, `analytics/examinations/<id>/publish/` | Evaluate an exam or publish its results |
