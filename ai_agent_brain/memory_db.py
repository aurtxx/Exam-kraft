"""Shared SQLite memory database for Exam-Kraft multi-agent coordination."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "agent_memory.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'P1',
                status TEXT NOT NULL DEFAULT 'PENDING',
                assigned_agent TEXT DEFAULT '',
                reported_by TEXT DEFAULT 'MANAGER',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                severity TEXT NOT NULL,
                area TEXT NOT NULL,
                finding TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def seed_initial_checklist() -> None:
    items = [
        ("UI/UX", "Responsive mobile & tablet CBT layout", "Ensure ExamCBTPage and QuestionPalette work cleanly on 768px-1366px viewports without horizontal scroll.", "P0", "MANAGER"),
        ("UI/UX", "Virtual calculator toggle in CBT toolbar", "Add optional draggable/dismissible calculator for numerical questions without covering the question stem.", "P1", "MANAGER"),
        ("UI/UX", "Consistent loading & empty states", "Replace bare spinners/blank screens on Student Dashboard, Staff Exams, and Analytics with clean skeletons and empty-state CTAs.", "P1", "MANAGER"),
        ("CBT Engine", "Server-authoritative submit_attempt (Codex P0)", "Derive final submission status/reason on the server from server_deadline and tab_switch_count.", "P0", "CODEX_REVIEW"),
        ("CBT Engine", "Monotonic performance.now() examClock (Codex P2)", "Use performance.now() in examClock.ts so OS clock changes cannot tamper with countdown.", "P1", "CODEX_REVIEW"),
        ("Backend", "Periodic expire_overdue_attempts command (Codex P0)", "Add Django management command to expire abandoned IN_PROGRESS attempts past hard_deadline.", "P0", "CODEX_REVIEW"),
        ("Backend", "Atomic batch-submit pending_responses (Codex P1)", "Allow submit_attempt to accept pending_responses inside the same transaction.atomic() lock.", "P1", "CODEX_REVIEW"),
        ("Testing", "End-to-end smoke test of live login & exam flow", "Verify staff login, student login, and exam delivery against live :8000 and :5173.", "P0", "MANAGER"),
    ]
    with get_conn() as conn:
        for cat, title, desc, prio, rep in items:
            conn.execute(
                """
                INSERT OR IGNORE INTO checklist_items (category, title, description, priority, reported_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cat, title, desc, prio, rep),
            )


if __name__ == "__main__":
    init_db()
    seed_initial_checklist()
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0]
    print(f"Initialized {DB_PATH} with {count} checklist items.")
