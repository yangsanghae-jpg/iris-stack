import json
import os
import sqlite3
import time
from typing import Any

import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel

APP_NAME = "iris-memory-admin"
IRIS_MEMORY_BASE_URL = os.getenv("IRIS_MEMORY_BASE_URL", "http://host.docker.internal:8001").rstrip("/")
IRIS_MEMORY_DB_PATH = os.getenv("IRIS_MEMORY_DB_PATH", "/app/data/memory.db")

app = FastAPI(title=APP_NAME)
templates = Jinja2Templates(directory="/app/app/templates")


class PrefetchPreviewRequest(BaseModel):
    user_id: str = "iris"
    project_id: str = "iris-stack"
    query: str


def _db_exists() -> bool:
    return os.path.exists(IRIS_MEMORY_DB_PATH)


def _connect_ro() -> sqlite3.Connection | None:
    if not _db_exists():
        return None
    uri = f"file:{IRIS_MEMORY_DB_PATH}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _safe_text(v: Any, limit: int = 500) -> Any:
    if not isinstance(v, str):
        return v
    s = v.strip()
    if len(s) <= limit:
        return s
    return s[:limit] + " ...[truncated]"


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = cur.fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _pick_order_column(conn: sqlite3.Connection, table: str) -> str:
    if _column_exists(conn, table, "updated_at"):
        return "updated_at"
    if _column_exists(conn, table, "created_at"):
        return "created_at"
    if _column_exists(conn, table, "id"):
        return "id"
    return "rowid"


def _parse_json_field(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return s
    if not ((s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]"))):
        return _safe_text(s)
    try:
        return json.loads(s)
    except Exception:
        return _safe_text(s)


def _rows_to_dicts(cur: sqlite3.Cursor, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    colnames = [d[0] for d in cur.description] if cur.description else []
    out: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for i, c in enumerate(colnames):
            val = row[i]
            if c.endswith("_json"):
                val = _parse_json_field(val)
            elif isinstance(val, str):
                val = _safe_text(val, 500)
            item[c] = val
        out.append(item)
    return out


def _select_recent(conn: sqlite3.Connection, table: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(conn, table):
        return []
    order_col = _pick_order_column(conn, table)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    return _rows_to_dicts(cur, rows)


def _build_memory_context_preview(prefetch_json: dict[str, Any], max_chars: int = 2000) -> str:
    packet = prefetch_json.get("packet") or {}
    lines: list[str] = [
        "[IRIS_MEMORY_CONTEXT]",
        f"- user_id: {prefetch_json.get('user_id', '')}",
        f"- project_id: {prefetch_json.get('project_id', '')}",
    ]
    project_context = list(packet.get("project_context") or [])
    related_tasks = list(packet.get("related_tasks") or [])
    reusable_skills = list(packet.get("reusable_skills") or [])

    if project_context:
        lines.append("[related project context]")
        for row in project_context[:8]:
            lines.append(f"- [{row.get('category', '')}] {row.get('title', '')}: {_safe_text(row.get('content', ''), 200)}")
    if related_tasks:
        lines.append("[related tasks]")
        for row in related_tasks[:8]:
            lines.append(f"- {row.get('task_id', '')}: {_safe_text(row.get('title', ''), 160)} (status={row.get('status', '')})")
    if reusable_skills:
        lines.append("[reusable skills]")
        for row in reusable_skills[:8]:
            lines.append(f"- {row.get('skill_id', '')}: {_safe_text(row.get('title', ''), 160)}")
    lines.append("[/IRIS_MEMORY_CONTEXT]")
    out = "\n".join(lines)
    if len(out) > max_chars:
        return out[: max_chars - 18] + "\n...[truncated]"
    return out


def _memory_health_ok() -> bool:
    try:
        r = requests.get(f"{IRIS_MEMORY_BASE_URL}/health", timeout=5)
        if not r.ok:
            return False
        data = r.json()
        return isinstance(data, dict) and data.get("status") == "ok"
    except Exception:
        return False


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "app": APP_NAME,
        "db_exists": _db_exists(),
        "memory_health_ok": _memory_health_ok(),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": APP_NAME,
            "memory_base_url": IRIS_MEMORY_BASE_URL,
            "db_path": IRIS_MEMORY_DB_PATH,
            "ts": int(time.time()),
        },
    )


@app.get("/api/summary")
def api_summary() -> dict[str, Any]:
    if not _db_exists():
        return {
            "ok": True,
            "db_path": IRIS_MEMORY_DB_PATH,
            "tables": {
                "user_profiles": 0,
                "project_memories": 0,
                "task_histories": 0,
                "skill_memories": 0,
            },
            "recent_tasks": [],
            "project_memories": [],
            "skill_memories": [],
            "user_profiles": [],
        }

    conn = None
    try:
        conn = _connect_ro()
        if conn is None:
            raise RuntimeError("db connect failed")
        return {
            "ok": True,
            "db_path": IRIS_MEMORY_DB_PATH,
            "tables": {
                "user_profiles": _count_rows(conn, "user_profiles"),
                "project_memories": _count_rows(conn, "project_memories"),
                "task_histories": _count_rows(conn, "task_histories"),
                "skill_memories": _count_rows(conn, "skill_memories"),
            },
            "recent_tasks": _select_recent(conn, "task_histories", 30),
            "project_memories": _select_recent(conn, "project_memories", 20),
            "skill_memories": _select_recent(conn, "skill_memories", 20),
            "user_profiles": _select_recent(conn, "user_profiles", 50),
        }
    except Exception as e:
        return {
            "ok": False,
            "db_path": IRIS_MEMORY_DB_PATH,
            "error": str(e),
            "tables": {
                "user_profiles": 0,
                "project_memories": 0,
                "task_histories": 0,
                "skill_memories": 0,
            },
            "recent_tasks": [],
            "project_memories": [],
            "skill_memories": [],
            "user_profiles": [],
        }
    finally:
        if conn is not None:
            conn.close()


@app.post("/api/prefetch-preview")
def api_prefetch_preview(body: PrefetchPreviewRequest) -> dict[str, Any]:
    req_json = {
        "user_id": body.user_id,
        "project_id": body.project_id,
        "query": body.query,
    }
    try:
        r = requests.post(f"{IRIS_MEMORY_BASE_URL}/memory/prefetch", json=req_json, timeout=15)
        r.raise_for_status()
        data = r.json() if r.content else {}
        if not isinstance(data, dict):
            data = {}
        preview = _build_memory_context_preview(data)
        return {
            "ok": True,
            "memory_used": True,
            "memory_context_preview": preview,
            "raw": data,
        }
    except Exception as e:
        return {
            "ok": False,
            "memory_used": False,
            "memory_context_preview": "",
            "error": str(e),
            "raw": {},
        }
