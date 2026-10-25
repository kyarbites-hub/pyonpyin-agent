"""SQLite persistence and an atomic, durable queue for a single-host MVP."""

import json
import os
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

from pyonpyin.core import utc_now
from pyonpyin.sheets import SheetsStore

KEYS = {
    "Site Settings": "setting_id",
    "Story Library": "story_id", "Story Text": "text_key", "Story Production": "story_id",
    "Story Episodes": "episode_key", "Processing History": "processing_id",
    "Publishing History": "publication_id",
}


class SQLiteStore(SheetsStore):
    """Reuse text/episode rules without connecting to any Google service."""

    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("PYONPYIN_DATABASE_PATH", "data/runtime/pyonpyin.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._active = None
        self.ensure_schema()

    @contextmanager
    def connection(self):
        if self._active is not None:
            yield self._active
            return
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        # ဖတ်ပြီးရေးမှုတစ်စုကို transaction တစ်ခုအဖြစ် သော့ခတ်၍ publish/edit ပြိုင်မှုကို ကာကွယ်သည်။
        if self._active is not None:
            yield self
            return
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._active = connection
            try:
                yield self
            finally:
                self._active = None

    def ensure_schema(self):
        with self.connection() as connection:
            if connection.execute("PRAGMA user_version").fetchone()[0] == 1:
                return
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    collection TEXT NOT NULL, record_key TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(collection, record_key)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, story_id TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    lease_until REAL NOT NULL DEFAULT 0, owner TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_story_job
                ON jobs(story_id) WHERE status IN ('QUEUED','RUNNING');
                CREATE TABLE IF NOT EXISTS login_attempts (address TEXT NOT NULL, attempted REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS login_attempt_window ON login_attempts(address, attempted);
            """)
            connection.execute("PRAGMA user_version=1")

    def read_records(self, sheet_name):
        self._check_sheet(sheet_name)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM records WHERE collection=? ORDER BY rowid", (sheet_name,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def upsert_many(self, sheet_name, key_column, records):
        self._check_sheet(sheet_name)
        if key_column != KEYS[sheet_name]:
            raise ValueError("Unexpected collection key.")
        keys = []
        with self.transaction():
            for record in records:
                key = str(record.get(key_column, ""))
                if not key:
                    raise ValueError(f"{key_column} is required.")
                old = self._active.execute(
                    "SELECT payload FROM records WHERE collection=? AND record_key=?",
                    (sheet_name, key),
                ).fetchone()
                merged = {**(json.loads(old[0]) if old else {}), **record}
                self._active.execute(
                    "INSERT INTO records VALUES(?,?,?) ON CONFLICT(collection,record_key) "
                    "DO UPDATE SET payload=excluded.payload",
                    (sheet_name, key, json.dumps(merged, ensure_ascii=False)),
                )
                keys.append(key)
        return keys

    def enqueue_job(self, story_id, kind):
        if kind not in {"GENERATE", "AUDIO", "DISCOVER"}:
            raise ValueError("Unsupported job kind.")
        with self.transaction():
            active = self._active.execute(
                "SELECT * FROM jobs WHERE story_id=? AND status IN ('QUEUED','RUNNING')",
                (story_id,),
            ).fetchone()
            if active:
                if active["kind"] != kind:
                    raise ValueError("Another job is already active for this story.")
                return dict(active)
            job_id, now = uuid.uuid4().hex, utc_now()
            self._active.execute(
                "INSERT INTO jobs(job_id,story_id,kind,status,created_at,updated_at) "
                "VALUES(?,?,?,'QUEUED',?,?)", (job_id, story_id, kind, now, now),
            )
            return dict(self._active.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone())

    def claim_job(self, owner, lease_seconds=900):
        with self.transaction():
            # Process ပျက်သွားသောအလုပ်ကို အလိုအလျောက် ထပ်မခေါ်ပါ။ Bill နှစ်ခါမဖြစ်စေရန် လူက retry ရွေးရသည်။
            self._active.execute(
                "UPDATE jobs SET status='INTERRUPTED', error='Worker stopped; review before retry.', "
                "updated_at=? WHERE status='RUNNING' AND lease_until<?", (utc_now(), time.time()),
            )
            row = self._active.execute(
                "SELECT * FROM jobs WHERE status='QUEUED' ORDER BY created_at, rowid LIMIT 1"
            ).fetchone()
            if not row:
                return None
            self._active.execute(
                "UPDATE jobs SET status='RUNNING', owner=?, lease_until=?, updated_at=? WHERE job_id=?",
                (owner, time.time() + lease_seconds, utc_now(), row["job_id"]),
            )
            return dict(self._active.execute("SELECT * FROM jobs WHERE job_id=?", (row["job_id"],)).fetchone())

    def finish_job(self, job_id, owner, error=""):
        with self.connection() as connection:
            changed = connection.execute(
                "UPDATE jobs SET status=?,error=?,updated_at=?,lease_until=0 "
                "WHERE job_id=? AND owner=? AND status='RUNNING' AND lease_until>=?",
                ("FAILED" if error else "SUCCEEDED", error, utc_now(), job_id, owner, time.time()),
            ).rowcount
        if changed != 1:
            raise RuntimeError("Job lease was lost; reconcile before retrying.")

    def list_jobs(self):
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 100"
            )]

    def has_active_job(self, story_id):
        with self.connection() as connection:
            return connection.execute(
                "SELECT 1 FROM jobs WHERE story_id=? AND status IN ('QUEUED','RUNNING') LIMIT 1",
                (story_id,),
            ).fetchone() is not None

    def allow_login_attempt(self, address, limit=10, window=300):
        now = time.time()
        with self.transaction():
            self._active.execute("DELETE FROM login_attempts WHERE attempted<?", (now - window,))
            count = self._active.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE address=?", (address,)
            ).fetchone()[0]
            if count >= limit:
                return False
            self._active.execute("INSERT INTO login_attempts VALUES(?,?)", (address, now))
            return True

    def backup(self, target):
        # SQLite backup API သုံးသဖြင့် WAL ပါသော database ကိုလည်း ကိုက်ညီစွာ backup ယူနိုင်သည်။
        target = Path(target)
        if target.resolve() == self.path.resolve() or target.exists():
            raise ValueError("Choose a new backup filename.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as source:
            with closing(sqlite3.connect(str(target))) as destination:
                source.backup(destination)
