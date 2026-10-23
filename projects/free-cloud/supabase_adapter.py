"""SUPABASE ADAPTER (free-cloud W2 - first in expansion order).

One task-store interface, two backends:
- LocalStandIn: SQLite (stdlib) with the SAME row shape the Micro's
  Door store uses (id, client, kind, text, status, result). Cage
  tests run against this until the real project exists.
- SupabaseStore: talks to a Supabase project's PostgREST endpoint
  with the service key read from the environment ONLY (the Vault
  pattern - never in code, chat, or files). Without configuration
  it raises NotConfigured; it never invents a connection.

Graduation to LIVE still requires Sayed's GitHub-OAuth project
creation tap + a live health check + one gated smoke task.
"""
import json
import os
import sqlite3
import urllib.request


class NotConfigured(Exception):
    pass


class LocalStandIn:
    name = "local-standin"

    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS tasks "
            "(id INTEGER PRIMARY KEY, client TEXT, kind TEXT, text TEXT, "
            "status TEXT DEFAULT 'queued', result TEXT)")
        self.db.commit()

    def put_task(self, client, kind, text):
        cur = self.db.execute(
            "INSERT INTO tasks (client, kind, text) VALUES (?, ?, ?)",
            (client, kind, text))
        self.db.commit()
        return cur.lastrowid

    def get_task(self, task_id):
        row = self.db.execute(
            "SELECT id, client, kind, text, status, result FROM tasks WHERE id=?",
            (task_id,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "client": row[1], "kind": row[2],
                "text": row[3], "status": row[4], "result": row[5]}

    def put_result(self, task_id, result, status="completed"):
        self.db.execute("UPDATE tasks SET result=?, status=? WHERE id=?",
                        (result, status, task_id))
        self.db.commit()
        return self.get_task(task_id)

    def count(self, status=None):
        if status:
            return self.db.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=?", (status,)).fetchone()[0]
        return self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    def health(self):
        try:
            self.db.execute("SELECT 1").fetchone()
            return {"ok": True, "backend": self.name, "tasks": self.count()}
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "backend": self.name, "error": str(exc)}


class SupabaseStore:
    name = "supabase"

    def __init__(self, url=None, key=None):
        self.url = (url or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.key = key or os.environ.get("SUPABASE_SERVICE_KEY") or ""
        if not self.url or not self.key:
            raise NotConfigured(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY not set - project "
                "creation is Sayed's batched OAuth tap (VERIFY-LATER)")

    def _req(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.url + path, data=data, method=method,
            headers={"apikey": self.key,
                     "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else None

    def put_task(self, client, kind, text):
        rows = self._req("POST", "/rest/v1/tasks",
                         {"client": client, "kind": kind, "text": text})
        return rows[0]["id"]

    def get_task(self, task_id):
        rows = self._req("GET", f"/rest/v1/tasks?id=eq.{task_id}&select=*")
        return rows[0] if rows else None

    def put_result(self, task_id, result, status="completed"):
        self._req("PATCH", f"/rest/v1/tasks?id=eq.{task_id}",
                  {"result": result, "status": status})
        return self.get_task(task_id)

    def count(self, status=None):
        raise NotImplementedError("count via PostgREST range header - wired at go-live")

    def health(self):
        try:
            self._req("GET", "/rest/v1/tasks?select=id&limit=1")
            return {"ok": True, "backend": self.name}
        except Exception as exc:
            return {"ok": False, "backend": self.name, "error": str(exc)}


def from_env():
    """Configured Supabase when credentials exist, else the stand-in.
    The fallback is explicit in the returned object's name - callers
    must not report stand-in results as a live expansion."""
    try:
        return SupabaseStore()
    except NotConfigured:
        return LocalStandIn()
