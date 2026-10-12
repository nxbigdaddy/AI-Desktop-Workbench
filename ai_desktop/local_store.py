from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_profile (
    user_id TEXT PRIMARY KEY,
    wecom_userid TEXT NOT NULL,
    display_name TEXT NOT NULL,
    department_code TEXT NOT NULL DEFAULT '',
    is_admin INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_metadata (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    credential_ref TEXT NOT NULL,
    idle_timeout_days INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    last_verified_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    server_updated_at TEXT,
    sync_state TEXT NOT NULL DEFAULT 'synced',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model_request_id TEXT,
    sync_state TEXT NOT NULL DEFAULT 'synced',
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_local_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS prompt_cache (
    prompt_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    version INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    variables_schema_json TEXT NOT NULL,
    allowed_tools_json TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    expires_at TEXT,
    content_hash TEXT NOT NULL,
    synced_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_cache_name_version
    ON prompt_cache(name, version);

CREATE TABLE IF NOT EXISTS usage_cache (
    request_id TEXT PRIMARY KEY,
    logical_model TEXT NOT NULL,
    actual_model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    usage_source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_outbox (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    next_attempt_at TEXT
);
"""


class LocalStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.executescript(SCHEMA)
        self.connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, ?)",
            (utc_iso(),),
        )
        self.connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                yield self.connection
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def get_or_create_device_id(self) -> str:
        with self._lock:
            row = self.connection.execute(
                "SELECT value_json FROM app_settings WHERE key='device_id'"
            ).fetchone()
            if row:
                return str(json.loads(row["value_json"]))
            device_id = str(uuid.uuid4())
            self.set_setting("device_id", device_id)
            return device_id

    def set_setting(self, key: str, value: Any) -> None:
        with self._lock:
            self.connection.execute(
                """INSERT INTO app_settings(key, value_json, updated_at)
                VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET
                value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (key, json.dumps(value, ensure_ascii=False), utc_iso()),
            )
            self.connection.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self.connection.execute(
                "SELECT value_json FROM app_settings WHERE key=?", (key,)
            ).fetchone()
            return json.loads(row["value_json"]) if row else default

    def latest_login(self) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                """SELECT auth_metadata.*, local_profile.wecom_userid,
                    local_profile.display_name, local_profile.department_code,
                    local_profile.is_admin
                FROM auth_metadata
                JOIN local_profile ON local_profile.user_id = auth_metadata.user_id
                ORDER BY auth_metadata.last_verified_at DESC
                LIMIT 1"""
            ).fetchone()
            return dict(row) if row else None

    def touch_login(self, session_id: str) -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE auth_metadata SET last_verified_at=? WHERE session_id=?",
                (utc_iso(), session_id),
            )
            self.connection.commit()

    def delete_login(self, session_id: str) -> None:
        with self._lock:
            self.connection.execute(
                "DELETE FROM auth_metadata WHERE session_id=?", (session_id,)
            )
            self.connection.commit()

    def save_login(
        self,
        *,
        user: dict[str, Any],
        session_id: str,
        device_id: str,
        credential_ref: str,
        idle_timeout_days: int,
    ) -> None:
        now = utc_iso()
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO local_profile(
                    user_id, wecom_userid, display_name, department_code, is_admin, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET
                    wecom_userid=excluded.wecom_userid,
                    display_name=excluded.display_name,
                    department_code=excluded.department_code,
                    is_admin=excluded.is_admin,
                    updated_at=excluded.updated_at""",
                (
                    user["id"],
                    user["wecom_userid"],
                    user["display_name"],
                    user.get("department_code", ""),
                    int(bool(user.get("is_admin"))),
                    now,
                ),
            )
            connection.execute(
                """INSERT INTO auth_metadata(
                    session_id, user_id, device_id, credential_ref,
                    idle_timeout_days, created_at, last_verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET
                    credential_ref=excluded.credential_ref,
                    idle_timeout_days=excluded.idle_timeout_days,
                    last_verified_at=excluded.last_verified_at""",
                (
                    session_id,
                    user["id"],
                    device_id,
                    credential_ref,
                    idle_timeout_days,
                    now,
                    now,
                ),
            )

    def save_conversation(self, conversation: dict[str, Any]) -> None:
        now = utc_iso()
        with self._lock:
            self.connection.execute(
                """INSERT INTO conversations(
                    id, title, server_updated_at, sync_state, created_at, updated_at
                ) VALUES (?, ?, ?, 'synced', ?, ?) ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    server_updated_at=excluded.server_updated_at,
                    sync_state='synced',
                    updated_at=excluded.updated_at""",
                (
                    conversation["id"],
                    conversation["title"],
                    conversation.get("updated_at"),
                    conversation.get("created_at", now),
                    now,
                ),
            )
            self.connection.commit()

    def save_chat_response(
        self,
        *,
        user_content: str,
        response: dict[str, Any],
    ) -> None:
        now = utc_iso()
        with self.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO messages(
                    id, conversation_id, role, content, model_request_id, created_at
                ) VALUES (?, ?, 'user', ?, ?, ?)""",
                (
                    response["user_message_id"],
                    response["conversation_id"],
                    user_content,
                    response["usage"]["request_id"],
                    now,
                ),
            )
            connection.execute(
                """INSERT OR IGNORE INTO messages(
                    id, conversation_id, role, content, model_request_id, created_at
                ) VALUES (?, ?, 'assistant', ?, ?, ?)""",
                (
                    response["assistant_message_id"],
                    response["conversation_id"],
                    response["content"],
                    response["usage"]["request_id"],
                    now,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (now, response["conversation_id"]),
            )
            usage = response["usage"]
            connection.execute(
                """INSERT OR IGNORE INTO usage_cache(
                    request_id, logical_model, actual_model, input_tokens,
                    output_tokens, total_tokens, usage_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    usage["request_id"],
                    usage["logical_model"],
                    usage["actual_model"],
                    usage["input_tokens"],
                    usage["output_tokens"],
                    usage["total_tokens"],
                    usage["source"],
                    now,
                ),
            )

    def replace_prompts(self, prompts: list[dict[str, Any]]) -> None:
        import hashlib

        now = utc_iso()
        active_ids = {str(item["id"]) for item in prompts}
        with self.transaction() as connection:
            for prompt in prompts:
                content_hash = hashlib.sha256(
                    str(prompt["system_prompt"]).encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """INSERT INTO prompt_cache(
                        prompt_id, name, purpose, version, system_prompt,
                        variables_schema_json, allowed_tools_json, required,
                        expires_at, content_hash, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(prompt_id) DO UPDATE SET
                        name=excluded.name,
                        purpose=excluded.purpose,
                        version=excluded.version,
                        system_prompt=excluded.system_prompt,
                        variables_schema_json=excluded.variables_schema_json,
                        allowed_tools_json=excluded.allowed_tools_json,
                        required=excluded.required,
                        expires_at=excluded.expires_at,
                        content_hash=excluded.content_hash,
                        synced_at=excluded.synced_at""",
                    (
                        prompt["id"],
                        prompt["name"],
                        prompt["purpose"],
                        prompt["version"],
                        prompt["system_prompt"],
                        json.dumps(prompt.get("variables_schema", {}), ensure_ascii=False),
                        json.dumps(prompt.get("allowed_tools", []), ensure_ascii=False),
                        int(bool(prompt.get("required", True))),
                        prompt.get("expires_at"),
                        content_hash,
                        now,
                    ),
                )
            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                connection.execute(
                    f"DELETE FROM prompt_cache WHERE prompt_id NOT IN ({placeholders})",
                    tuple(sorted(active_ids)),
                )
            else:
                connection.execute("DELETE FROM prompt_cache")

    def list_prompts(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(row)
                for row in self.connection.execute(
                    "SELECT * FROM prompt_cache ORDER BY name, version DESC"
                ).fetchall()
            ]
