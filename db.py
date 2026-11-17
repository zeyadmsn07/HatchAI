import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "hatchai.db")


def _db_path():
    return os.environ.get("DB_PATH", DB_PATH)


def _is_test_db():
    """True when DB_PATH points to a temporary/test file (not the default)."""
    p = _db_path()
    return p != DB_PATH and p != "hatchai.db" and (
        "tmp" in p.lower() or "temp" in p.lower() or ":memory:" in p
    )


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                phase INTEGER DEFAULT 0,
                founder_token TEXT NOT NULL,
                brief_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error TEXT,
                auto_approve INTEGER DEFAULT 0
            );
        """)
        # Migrations for existing DBs
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN auto_approve INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass  # column already exists
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS gate_results (
                run_id TEXT NOT NULL,
                gate_id INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                evidence_score REAL DEFAULT 0,
                viability_score REAL DEFAULT 0,
                reason TEXT,
                checks_json TEXT DEFAULT '{}',
                founder_decision TEXT,
                founder_override INTEGER DEFAULT 0,
                override_reason TEXT DEFAULT '',
                decided_at TEXT,
                pivot_to TEXT DEFAULT '',
                PRIMARY KEY (run_id, gate_id)
            );
            CREATE TABLE IF NOT EXISTS decision_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                sources_json TEXT DEFAULT '[]',
                model TEXT,
                cost REAL DEFAULT 0,
                approved_by TEXT,
                phase INTEGER,
                outcome TEXT,
                tokens INTEGER
            );
        """)
        try:
            conn.execute("ALTER TABLE gate_results ADD COLUMN pivot_to TEXT DEFAULT ''")
        except Exception:
            pass
        for stmt in ("ALTER TABLE runs ADD COLUMN scoring_version TEXT",
                     "ALTER TABLE decision_log ADD COLUMN scoring_version TEXT"):
            try:
                conn.execute(stmt)
            except Exception:
                pass


@contextmanager
def get_conn():  # noqa: D401
    conn = sqlite3.connect(_db_path(), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_run(run_id, founder_token, brief_json, created_at, auto_approve=False):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, status, phase, founder_token, brief_json, created_at, updated_at, auto_approve) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "created", 0, founder_token, brief_json, created_at, created_at, 1 if auto_approve else 0),
        )


def get_run(run_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def update_run_status(run_id, status, phase=None, error=None):
    ts = now_iso()
    with get_conn() as conn:
        if phase is not None:
            conn.execute(
                "UPDATE runs SET status=?, phase=?, updated_at=?, error=? WHERE run_id=?",
                (status, phase, ts, error, run_id),
            )
        else:
            conn.execute(
                "UPDATE runs SET status=?, updated_at=?, error=? WHERE run_id=?",
                (status, ts, error, run_id),
            )


def save_gate_result(run_id, gate_id, outcome, evidence_score, viability_score, reason, checks, pivot_to=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO gate_results "
            "(run_id, gate_id, outcome, evidence_score, viability_score, reason, checks_json, pivot_to) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, gate_id, outcome, evidence_score, viability_score, reason, json.dumps(checks), pivot_to or ""),
        )


def get_gate_result(run_id, gate_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gate_results WHERE run_id=? AND gate_id=?", (run_id, gate_id)
        ).fetchone()
        return dict(row) if row else None


def record_gate_decision(run_id, gate_id, decision, override_reason=""):
    ts = now_iso()
    is_override = 1 if decision == "override_stop" else 0
    with get_conn() as conn:
        conn.execute(
            "UPDATE gate_results SET founder_decision=?, founder_override=?, override_reason=?, decided_at=? "
            "WHERE run_id=? AND gate_id=?",
            (decision, is_override, override_reason, ts, run_id, gate_id),
        )


def set_run_scoring(run_id, version):
    with get_conn() as conn:
        conn.execute("UPDATE runs SET scoring_version=? WHERE run_id=?", (version, run_id))


def log_action(run_id, agent, action, sources=None, model=None, cost=0, approved_by=None,
               phase=None, outcome=None, tokens=None):
    ts = now_iso()
    with get_conn() as conn:
        row = conn.execute("SELECT scoring_version FROM runs WHERE run_id=?", (run_id,)).fetchone()
        conn.execute(
            "INSERT INTO decision_log "
            "(run_id, timestamp, agent, action, sources_json, model, cost, approved_by, phase, outcome, tokens, "
            "scoring_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, ts, agent, action, json.dumps(sources or []), model, cost or 0,
             approved_by, phase, outcome, tokens, row["scoring_version"] if row else None),
        )
    # decision_log.json is exported explicitly by the demo CLI (orchestrator.run_demo)
    # so that the committed file holds the demo runs only.


def get_log_entries(run_id=None, limit=200):
    with get_conn() as conn:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM decision_log WHERE run_id=? ORDER BY id ASC LIMIT ?",
                (run_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM decision_log ORDER BY id ASC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def export_decision_log(path="decision_log.json", run_ids=None):
    """Write the log as JSON. With run_ids, only those runs are exported (demo runs)."""
    entries = []
    with get_conn() as conn:
        if run_ids:
            q = ",".join("?" for _ in run_ids)
            rows = conn.execute(f"SELECT * FROM decision_log WHERE run_id IN ({q}) ORDER BY id ASC",
                                list(run_ids)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM decision_log ORDER BY id ASC").fetchall()
        for r in rows:
            d = dict(r)
            entry = {
                "timestamp": d["timestamp"],
                "agent": d["agent"],
                "action": d["action"],
                "sources": json.loads(d.get("sources_json") or "[]"),
                "model": d["model"],
                "cost": d["cost"],
                "approved_by": d["approved_by"],
            }
            if d.get("outcome"):
                entry["outcome"] = d["outcome"]
            if d.get("run_id"):
                entry["run_id"] = d["run_id"]
            if d.get("scoring_version"):
                entry["scoring_version"] = d["scoring_version"]
            entries.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    return entries


def get_all_runs():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]
