# New findings

## HB-001 · High · Concurrent writes fail in the SQLite audit environment

Concurrent attempt traffic returned intermittent HTTP 500 responses on exam starts, answer saves, and proctoring events. The Django log identified `django.db.utils.OperationalError: database is locked`. The ten candidate logs recorded 87 HTTP 500 responses (61 SAVE, 18 START, 8 TAB_SWITCH). The audit controller retried those writes and all ten attempts reached final states. This run establishes contention in the local SQLite configuration. PostgreSQL behavior remains unverified.

## HB-002 · Low · Delivery includes a field named key for the MCQ option label

All ten initial delivery payloads included the MCQ option display label under `key`, failing the literal CHECK-08 field rule. The capture showed no question-level key, numerical grading bounds, or option correctness flags in those payloads.
