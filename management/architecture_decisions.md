# Architecture Decision Records (ADR) — EZExam Reconstruction

**Document Version**: 1.0.0  
**Status**: Approved & Frozen  
**Author**: Agent 3 (System Architecture Analyst)  
**Date**: 2026-11-24  
**Project**: EZExam Reconstruction (Self-Hosted Examination Platform)  

---

## Index of Decisions

- [ADR-001: System Topology — Modular Monolith over Microservices](#adr-001-system-topology--modular-monolith-over-microservices)
- [ADR-002: Multi-Tenancy Strategy — Row-Level Isolation in Shared Schema](#adr-002-multi-tenancy-strategy--row-level-isolation-in-shared-schema)
- [ADR-003: Real-Time Timer & Heartbeat Protocol — Server-Authoritative Deadline](#adr-003-real-time-timer--heartbeat-protocol--server-authoritative-deadline)
- [ADR-004: Concurrency & Idempotency — Pessimistic Row Locking for Submissions](#adr-004-concurrency--idempotency--pessimistic-row-locking-for-submissions)
- [ADR-005: Evaluation Engine — Asynchronous Worker Pipeline via Celery and Redis](#adr-005-evaluation-engine--asynchronous-worker-pipeline-via-celery-and-redis)
- [ADR-006: Candidate Resilience — Dual-Tier Response Caching & Disconnect Recovery](#adr-006-candidate-resilience--dual-tier-response-caching--disconnect-recovery)
- [ADR-007: Containerized Gateway & Process Supervisor Stack](#adr-007-containerized-gateway--process-supervisor-stack)

---

## ADR-001: System Topology — Modular Monolith over Microservices

### Context
EZExam is required to operate as an independent, fully functional, self-hosted examination platform capable of supporting at least 100 simultaneous active test-takers per node, in both cloud WAN and air-gapped local area network (LAN) environments. We considered decomposing the system into separate microservices (Auth Service, Exam Service, Question Bank Service, Evaluation Service) versus structuring it as a cohesive modular monolith.

### Decision
We adopt a **Modular Monolith** architecture:
- **Backend**: Python 3.11+, Django 5+, Django REST Framework, Django Channels (ASGI). Code is divided strictly into domain apps (`accounts`, `organizations`, `question_bank`, `examinations`, `engine`, `evaluation`, `notices`).
- **Frontend**: Single Page Application (SPA) powered by React 18, TypeScript, Vite, and Tailwind CSS.
- **Persistence**: Single PostgreSQL 16 relational database with Redis 7 for cache and message brokering.

### Rationale
1. **Deployment Simplicity**: A modular monolith requires only a single Docker Compose deployment manifest with minimal memory footprint (< 1 GB RAM total), making it ideal for self-hosted educational institutions and offline campus servers.
2. **ACID Transaction Guarantees**: Exam submissions, question responses, and score calculations benefit from native relational database transactions without requiring complex distributed consensus or saga patterns.
3. **Low Latency**: In-process method calls eliminate network serialization hops between internal components during high-traffic exam starts.

### Consequences
- **Positive**: Simple development and debugging workflow, unified migrations, zero distributed transaction overhead, easy local testing.
- **Negative**: Requires strict discipline to enforce modular app boundaries within Django to prevent circular model dependencies.

---

## ADR-002: Multi-Tenancy Strategy — Row-Level Isolation in Shared Schema

### Context
The platform must support multiple tenant organizations (schools, coaching institutes, colleges) on a single self-hosted deployment. We evaluated three architectural patterns:
1. Database-per-tenant (separate PostgreSQL database for each institution).
2. Schema-per-tenant (PostgreSQL schemas separated via search path).
3. Shared database and shared schema with row-level filtering (`organization_id`).

### Decision
We adopt **Shared Database and Shared Schema with Row-Level Filtering (`organization_id`)**.
- Every tenant model inherits from `BaseTenantModel`.
- A dedicated `TenantManager` automatically filters all queries by the active tenant resolved from the request domain or JWT claim.
- All institutional foreign keys, codes, and roll numbers enforce composite uniqueness with `organization_id`.

### Rationale
1. **Migration Velocity**: Schema-per-tenant requires executing hundreds of DDL migrations across multiple schemas on upgrade, which is prone to migration locks and partial failures. Shared schema executes migrations instantaneously once.
2. **Resource Efficiency**: Connection pooling (via PgBouncer or Django persistent connections) is shared efficiently without separate connection pools per tenant.
3. **Cross-Tenant SuperAdmin Capabilities**: Allows platform administrators to manage institutions and aggregate global health metrics effortlessly.

### Consequences
- **Positive**: Fast migrations, low memory consumption, easy tenant onboarding.
- **Negative**: Requires rigorous testing and automated linter checks to ensure queries never bypass `TenantManager`.

---

## ADR-003: Real-Time Timer & Heartbeat Protocol — Server-Authoritative Deadline

### Context
In web-based examination platforms, relying on the client browser's local clock for test duration is a critical security vulnerability. Candidates can manipulate local system clocks, alter `setTimeout` loops in developer tools, or experience throttling when browser tabs are backgrounded.

### Decision
We implement a **Server-Authoritative Timer & Heartbeat Synchronization Protocol**:
1. **Immutable Server Deadline**: When an attempt starts, the server computes and persists:
   $$\text{server\_deadline} = \min(\text{started\_at} + \text{duration\_minutes}, \text{exam.end\_window})$$
2. **Real-Time Heartbeat Sync**:
   - The candidate frontend maintains a persistent WebSocket connection (`/ws/exam/{attempt_id}/`).
   - Every 15 seconds, a heartbeat ping/pong synchronizes the remaining time calculated exclusively from the server's authoritative clock.
   - If the WebSocket disconnects, the client falls back to periodic HTTP POST (`/api/v1/student/attempts/{attempt_id}/heartbeat/`).
3. **Server Enforced Grace Period**:
   - The server allows a configurable network grace period (default: 30 seconds) after `server_deadline`.
   - Any response received after `server_deadline + grace_period` is rejected with `403 FORBIDDEN` (`DEADLINE_EXPIRED`).
   - When the deadline expires, the server's periodic Celery task or worker automatically transitions the attempt to `AUTO_SUBMITTED`.

### Consequences
- **Positive**: Total elimination of client-side clock tampering; consistent and fair timing across varying client hardware.
- **Negative**: Requires clock synchronization (NTP) on host servers.

---

## ADR-004: Concurrency & Idempotency — Pessimistic Row Locking for Submissions

### Context
During examination completion, candidates frequently trigger duplicate submissions by double-clicking the submit button, refreshing the browser during network latency, or having multiple tabs open simultaneously. Duplicate submissions can cause race conditions, corrupt response states, or trigger concurrent evaluation tasks.

### Decision
We mandate **Idempotent Final Submissions protected by Database Pessimistic Locks**:
1. **Pessimistic Locking**: The submission handler wraps all state transitions inside `transaction.atomic()` using `select_for_update()`:
   ```python
   with transaction.atomic():
       attempt = ExaminationAttempt.objects.select_for_update().get(id=attempt_id)
       if attempt.status in [AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED]:
           return Response({
               "status": "SUCCESS", 
               "message": "Attempt already submitted",
               "submitted_at": attempt.submitted_at
           }, status=status.HTTP_200_OK)
       
       attempt.status = AttemptStatus.SUBMITTED
       attempt.submitted_at = timezone.now()
       attempt.save(update_fields=['status', 'submitted_at'])
   ```
2. **Idempotency Guarantee**: If an attempt is already marked `SUBMITTED` or `AUTO_SUBMITTED`, repeated requests return HTTP `200 OK` with the existing submission timestamp rather than throwing errors or re-evaluating.

### Consequences
- **Positive**: Zero duplicate submission entries; thread-safe handling under high concurrency.
- **Negative**: Row lock holds for the duration of the submission transaction (~5-15 milliseconds), which is well within acceptable performance bounds.

---

## ADR-005: Asynchronous Evaluation & Ranking Engine

### Context
When an examination window closes, dozens or hundreds of candidates submit within a short time window. Calculating scores, applying section penalties, computing ranks, and deriving cohort percentiles synchronously in the web request thread would exhaust web server workers and cause request timeouts.

### Decision
We decouple evaluation from the web request cycle using **Celery with Redis**:
1. Final submission changes the attempt status to `SUBMITTED` and enqueues a Celery task: `evaluate_attempt.delay(attempt_id)`.
2. When the exam window officially closes, an exam-level aggregation task (`compute_cohort_rankings.delay(exam_id)`) computes:
   - Total scores and section breakdown.
   - Fractional ranks with standard tie-breaking rules.
   - Cohort percentile:
     $$\text{Percentile} = \left( \frac{\text{Number of candidates with score} < S}{N} \right) \times 100$$
3. Results are saved in `evaluation_evaluationresult` and marked `is_published: false` until faculty explicitly release scores.

### Consequences
- **Positive**: Candidate submission returns in < 100ms; grading workload scales independently via Celery background workers.
- **Negative**: Requires running Redis and a Celery worker container alongside the web application.

---

## ADR-006: Candidate Resilience — Dual-Tier Response Caching & Disconnect Recovery

### Context
Educational testing environments frequently experience transient network drops, accidental tab closures, or power flickers. Candidates must never lose progress or answers during these events.

### Decision
We implement a **Dual-Tier Response Persistence Architecture**:
1. **Client Tier (Immediate)**: When a candidate selects an option or enters numerical text, the response is instantly written to the browser's `IndexedDB` / `localStorage` with a local timestamp. The question palette updates immediately to `ANSWERED` without waiting for network acknowledgment.
2. **Server Tier (Debounced Async)**: An autosave engine debounces updates (500ms) and transmits them to the server via WebSocket (or HTTP REST fallback). Once the server acknowledges persistence, the client marks the response as `SYNCED`.
3. **Session Recovery**: Upon browser refresh or reconnection on a different machine:
   - Client sends `attempt_token`.
   - Server returns the active attempt state, remaining duration, and all previously saved responses.
   - Client reconciles any unsynced offline responses with the server state based on highest timestamp.

### Consequences
- **Positive**: 100% data loss prevention; seamless continuation across accidental reloads or brief internet cuts.
- **Negative**: Client code must handle timestamp reconciliation on reconnect.

---

## ADR-007: Containerized Gateway & Process Supervisor Stack

### Context
The deployment stack must be reproducible, simple to run locally via Docker Compose, and suitable for LAN/WAN self-hosting.

### Decision
The stack is structured into isolated containers supervised by **Docker Compose**:
1. **`nginx`**: Reverse proxy and static file server (Vite frontend production build). Routes `/api/` to Django WSGI/ASGI, `/ws/` to Daphne ASGI, and all other traffic to React SPA.
2. **`backend`**: Django 5 + Daphne / Uvicorn ASGI server running the API and WebSocket handlers.
3. **`db`**: PostgreSQL 16 Alpine with persistent volume and optimized connection tuning.
4. **`redis`**: Redis 7 Alpine serving as Celery message broker and Channels layer.
5. **`celery_worker`**: Background worker running async evaluation and report generation tasks.

### Consequences
- **Positive**: Single-command startup (`docker compose up -d`), isolated dependencies, production-identical local development environment.
- **Negative**: Requires Docker daemon installed on the host machine.
