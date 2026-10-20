"""
app/storage.py - SQLite Repository with Short Parameterized Transactions & JSON Payloads.

Tables:
- user_settings
- drafts
- generation_requests
- scripts
- last_successful_scripts
- last_failed_requests
- idea_batches
- hook_options
- subscriptions
- schema_migrations

NOTE ON HOSTING DURABILITY:
SQLite on ephemeral container filesystems (e.g. standard Render.com free web instances)
is NOT durable across container replacement or redeployment. Persistent disk or external
database is required for durability across deployments. Restart persistence within the same
container does not guarantee durable hosting storage.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, List, Tuple, Dict, Any

from app.models import (
    UserKey,
    Draft,
    GenerationRequest,
    SavedScript,
    EvidenceRecord,
    Idea,
    ScriptPlan,
)

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, db_path: str = "bot_database.sqlite3", legacy_settings_path: Optional[str] = None, legacy_subs_path: Optional[str] = None):
        self.db_path = db_path
        self._legacy_settings_path = legacy_settings_path
        self._legacy_subs_path = legacy_subs_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    default_duration TEXT NOT NULL,
                    pace REAL NOT NULL,
                    niche TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    format_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    audience TEXT NOT NULL,
                    comedy_style TEXT,
                    actor_count INTEGER,
                    evidence_ids_json TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    niche TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            # Check PRAGMA for existing databases needing column additions
            cursor.execute("PRAGMA table_info(user_settings)")
            us_cols = [row["name"] for row in cursor.fetchall()]
            if "niche" not in us_cols:
                cursor.execute("ALTER TABLE user_settings ADD COLUMN niche TEXT")

            cursor.execute("PRAGMA table_info(drafts)")
            d_cols = [row["name"] for row in cursor.fetchall()]
            if "niche" not in d_cols:
                cursor.execute("ALTER TABLE drafts ADD COLUMN niche TEXT")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generation_requests (
                    id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    draft_snapshot_json TEXT NOT NULL,
                    pace REAL NOT NULL,
                    source_script_id TEXT,
                    source_script_version INTEGER,
                    selected_hook_json TEXT,
                    evidence_snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scripts (
                    id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    request_snapshot_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (id, version)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_successful_scripts (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    script_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_failed_requests (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    error_code TEXT NOT NULL,
                    user_message_km TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS idea_batches (
                    token TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    ideas_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hook_options (
                    token TEXT PRIMARY KEY,
                    script_id TEXT NOT NULL,
                    script_version INTEGER NOT NULL,
                    options_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    is_active INTEGER NOT NULL,
                    subscribed_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                )
            """)
            conn.commit()

        self._run_migrations()

    def _run_migrations(self):
        """Runs one-time safe migration from legacy JSON files without deleting originals."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if cursor.fetchone():
                return  # Migration already applied

            now_iso = datetime.now(timezone.utc).isoformat()
            logger.info("Running schema migration 1 (legacy JSON migration)...")

            # 1. Migrate user_settings.json
            legacy_settings_path = self._legacy_settings_path or "user_settings.json"
            if os.path.exists(legacy_settings_path):
                try:
                    with open(legacy_settings_path, "r", encoding="utf-8") as f:
                        old_settings = json.load(f)
                    for chat_id_str, vals in old_settings.items():
                        try:
                            cid = int(chat_id_str)
                            # In Telegram private chats, chat_id == user_id. For group chats (cid < 0),
                            # we preserve chat-scoped settings with user_id = cid to avoid assigning to an arbitrary user.
                            uid = cid
                            dur = vals.get("duration", "60 វិនាទី")
                            pace = float(vals.get("pace", 10.0))
                            cursor.execute("""
                                INSERT OR REPLACE INTO user_settings 
                                (chat_id, user_id, default_duration, pace, updated_at)
                                VALUES (?, ?, ?, ?, ?)
                            """, (cid, uid, dur, pace, now_iso))
                        except Exception as e:
                            logger.warning(f"Skipping malformed legacy setting {chat_id_str}: {e}")
                except Exception as e:
                    logger.error(f"Error reading legacy settings during migration: {e}")

            # 2. Migrate subscribers.json
            legacy_subs_path = self._legacy_subs_path or "subscribers.json"
            if os.path.exists(legacy_subs_path):
                try:
                    with open(legacy_subs_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    old_subs = loaded if isinstance(loaded, list) else loaded.get("subscribers", [])
                    for sub_id in old_subs:
                        try:
                            cid = int(sub_id)
                            uid = cid
                            cursor.execute("""
                                INSERT OR REPLACE INTO subscriptions
                                (chat_id, user_id, is_active, subscribed_at)
                                VALUES (?, ?, 1, ?)
                            """, (cid, uid, now_iso))
                        except Exception as e:
                            logger.warning(f"Skipping malformed legacy subscriber {sub_id}: {e}")
                except Exception as e:
                    logger.error(f"Error reading legacy subscribers during migration: {e}")

            cursor.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)", (now_iso,))
            conn.commit()
            logger.info("Schema migration 1 complete. Original JSON files preserved.")

    # ─────────────────────────────────────────────
    # Settings Operations
    # ─────────────────────────────────────────────
    def get_settings(self, user_key: UserKey, default_duration: str = "60 វិនាទី", default_pace: float = 10.0) -> dict:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT default_duration, pace, niche FROM user_settings
                WHERE chat_id = ? AND user_id = ?
            """, (user_key.chat_id, user_key.user_id))
            row = cursor.fetchone()
            if row:
                return {
                    "duration": row["default_duration"],
                    "pace": float(row["pace"]),
                    "niche": row["niche"] if ("niche" in row.keys() and row["niche"]) else None,
                }
            return {
                "duration": default_duration,
                "pace": default_pace,
                "niche": None,
            }

    def save_settings(self, user_key: UserKey, duration: str, pace: float, niche: Optional[str] = None):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if niche is None:
                cursor.execute("SELECT niche FROM user_settings WHERE chat_id = ? AND user_id = ?", (user_key.chat_id, user_key.user_id))
                r = cursor.fetchone()
                if r and "niche" in r.keys():
                    niche = r["niche"]
            cursor.execute("""
                INSERT OR REPLACE INTO user_settings
                (chat_id, user_id, default_duration, pace, niche, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_key.chat_id, user_key.user_id, duration, float(pace), niche, now_iso))
            conn.commit()

    def get_user_niche(self, user_key: UserKey) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT niche FROM user_settings WHERE chat_id = ? AND user_id = ?", (user_key.chat_id, user_key.user_id))
            row = cursor.fetchone()
            if row and "niche" in row.keys() and row["niche"]:
                return str(row["niche"]).strip()
            return None

    def save_user_niche(self, user_key: UserKey, niche: str):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT default_duration, pace FROM user_settings WHERE chat_id = ? AND user_id = ?", (user_key.chat_id, user_key.user_id))
            row = cursor.fetchone()
            dur = row["default_duration"] if row else "60 វិនាទី"
            pace = float(row["pace"]) if row else 10.0
            cursor.execute("""
                INSERT OR REPLACE INTO user_settings
                (chat_id, user_id, default_duration, pace, niche, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_key.chat_id, user_key.user_id, dur, pace, niche.strip(), now_iso))
            conn.commit()

    def clear_incompatible_drafts(self, user_key: UserKey):
        """Invalidates pending drafts and idea batches for user when changing niche, preserving successful scripts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drafts WHERE chat_id = ? AND user_id = ?", (user_key.chat_id, user_key.user_id))
            cursor.execute("DELETE FROM idea_batches WHERE chat_id = ? AND user_id = ?", (user_key.chat_id, user_key.user_id))
            conn.commit()

    # ─────────────────────────────────────────────
    # Draft Operations
    # ─────────────────────────────────────────────
    def get_draft(self, draft_id: str) -> Optional[Draft]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Draft(
                id=row["id"],
                revision=row["revision"],
                format_id=row["format_id"],
                topic=row["topic"],
                duration_seconds=row["duration_seconds"],
                audience=row["audience"],
                comedy_style=row["comedy_style"],
                actor_count=row["actor_count"],
                evidence_ids=json.loads(row["evidence_ids_json"]),
                current_step=row["current_step"],
                owner=UserKey(row["chat_id"], row["user_id"]),
                niche=row["niche"] if ("niche" in row.keys() and row["niche"]) else None,
            )

    def save_draft(self, user_key: UserKey, draft: Draft):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO drafts
                (id, chat_id, user_id, revision, format_id, topic, duration_seconds,
                 audience, comedy_style, actor_count, evidence_ids_json, current_step, niche, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                draft.id, user_key.chat_id, user_key.user_id, draft.revision,
                draft.format_id, draft.topic, draft.duration_seconds, draft.audience,
                draft.comedy_style, draft.actor_count, json.dumps(draft.evidence_ids),
                draft.current_step, draft.niche, now_iso
            ))
            conn.commit()

    # ─────────────────────────────────────────────
    # Generation Request Operations
    # ─────────────────────────────────────────────
    def save_generation_request(self, request: GenerationRequest):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO generation_requests
                (id, chat_id, user_id, operation, draft_snapshot_json, pace,
                 source_script_id, source_script_version, selected_hook_json,
                 evidence_snapshot_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.id, request.owner.chat_id, request.owner.user_id,
                request.operation, json.dumps(request.draft_snapshot, ensure_ascii=False),
                request.pace_units_per_second, request.source_script_id,
                request.source_script_version,
                json.dumps(request.selected_hook, ensure_ascii=False) if request.selected_hook else None,
                json.dumps([e.to_dict() for e in request.evidence_snapshot], ensure_ascii=False),
                now_iso
            ))
            conn.commit()

    def get_generation_request(self, request_id: str) -> Optional[GenerationRequest]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM generation_requests WHERE id = ?", (request_id,))
            row = cursor.fetchone()
            if not row:
                return None
            ev_list = [EvidenceRecord.from_dict(e) for e in json.loads(row["evidence_snapshot_json"])]
            hook_dict = json.loads(row["selected_hook_json"]) if row["selected_hook_json"] else None
            return GenerationRequest(
                id=row["id"],
                operation=row["operation"],
                owner=UserKey(row["chat_id"], row["user_id"]),
                draft_snapshot=json.loads(row["draft_snapshot_json"]),
                pace_units_per_second=float(row["pace"]),
                source_script_id=row["source_script_id"],
                source_script_version=row["source_script_version"],
                selected_hook=hook_dict,
                evidence_snapshot=ev_list,
            )

    # ─────────────────────────────────────────────
    # Script Operations (Atomic Transaction)
    # ─────────────────────────────────────────────
    def save_successful_script(self, script: SavedScript):
        """
        Saves script version and updates last_successful_scripts pointer ATOMICALLY
        in the exact same database transaction.
        """
        script_dict = script.to_dict()
        now_iso = script.created_at.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Save generation request snapshot if not already saved
            self.save_generation_request(script.request_snapshot)

            # 2. Insert into scripts
            cursor.execute("""
                INSERT OR REPLACE INTO scripts
                (id, version, chat_id, user_id, request_snapshot_json, plan_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                script.id,
                script.version,
                script.owner.chat_id,
                script.owner.user_id,
                json.dumps(script_dict["request_snapshot"], ensure_ascii=False),
                json.dumps(script_dict["plan"], ensure_ascii=False),
                now_iso
            ))

            # 3. Update last_successful_scripts pointer atomically
            cursor.execute("""
                INSERT OR REPLACE INTO last_successful_scripts
                (chat_id, user_id, script_id, version, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                script.owner.chat_id,
                script.owner.user_id,
                script.id,
                script.version,
                now_iso
            ))
            conn.commit()

    def get_script(self, script_id: str, version: int) -> Optional[SavedScript]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scripts WHERE id = ? AND version = ?
            """, (script_id, version))
            row = cursor.fetchone()
            if not row:
                return None
            d = {
                "id": row["id"],
                "version": row["version"],
                "owner": f"{row['chat_id']}:{row['user_id']}",
                "request_snapshot": json.loads(row["request_snapshot_json"]),
                "plan": json.loads(row["plan_json"]),
                "created_at": row["created_at"],
            }
            return SavedScript.from_dict(d)

    def get_last_successful_script(self, user_key: UserKey) -> Optional[SavedScript]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT script_id, version FROM last_successful_scripts
                WHERE chat_id = ? AND user_id = ?
            """, (user_key.chat_id, user_key.user_id))
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_script(row["script_id"], row["version"])

    # ─────────────────────────────────────────────
    # Failure Operations (Never touches last_successful_scripts)
    # ─────────────────────────────────────────────
    def save_failed_request(self, user_key: UserKey, request: GenerationRequest, error_code: str, user_message_km: str):
        now_iso = datetime.now(timezone.utc).isoformat()
        self.save_generation_request(request)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO last_failed_requests
                (chat_id, user_id, request_id, error_code, user_message_km, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_key.chat_id, user_key.user_id, request.id, error_code, user_message_km, now_iso))
    save_last_failed_request = save_failed_request

    def get_last_failed_request(self, user_key: UserKey) -> Optional[Tuple[GenerationRequest, str, str]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT request_id, error_code, user_message_km FROM last_failed_requests
                WHERE chat_id = ? AND user_id = ?
            """, (user_key.chat_id, user_key.user_id))
            row = cursor.fetchone()
            if not row:
                return None
            req = self.get_generation_request(row["request_id"])
            if not req:
                return None
            return req, row["error_code"], row["user_message_km"]

    # ─────────────────────────────────────────────
    # Ideas & Evidence Batches
    # ─────────────────────────────────────────────
    def save_idea_batch(self, token: str, user_key: UserKey, category: str, ideas: List[Idea], evidence: List[EvidenceRecord]):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO idea_batches
                (token, chat_id, user_id, category, ideas_json, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                token, user_key.chat_id, user_key.user_id, category,
                json.dumps([i.to_dict() for i in ideas], ensure_ascii=False),
                json.dumps([e.to_dict() for e in evidence], ensure_ascii=False),
                now_iso
            ))
            conn.commit()

    def get_idea_batch(self, token: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM idea_batches WHERE token = ?", (token,))
            row = cursor.fetchone()
            if not row:
                return None
            ideas = [Idea.from_dict(i) for i in json.loads(row["ideas_json"])]
            evidence = [EvidenceRecord.from_dict(e) for e in json.loads(row["evidence_json"])]
            return {
                "token": row["token"],
                "owner": UserKey(row["chat_id"], row["user_id"]),
                "category": row["category"],
                "ideas": ideas,
                "evidence": evidence,
                "created_at": row["created_at"],
            }

    def get_recent_evidence_for_user(self, user_key: UserKey, evidence_ids: List[str]) -> List[EvidenceRecord]:
        """Retrieves EvidenceRecord objects matching evidence_ids from recent idea batches."""
        if not evidence_ids:
            return []
        ids_set = {str(eid) for eid in evidence_ids}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT evidence_json FROM idea_batches
                WHERE chat_id = ? AND user_id = ?
                ORDER BY created_at DESC LIMIT 10
            """, (user_key.chat_id, user_key.user_id))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute("""
                    SELECT evidence_json FROM idea_batches
                    ORDER BY created_at DESC LIMIT 10
                """)
                rows = cursor.fetchall()

            found: Dict[str, EvidenceRecord] = {}
            for row in rows:
                try:
                    ev_list = [EvidenceRecord.from_dict(e) for e in json.loads(row["evidence_json"])]
                    for ev in ev_list:
                        if str(ev.id) in ids_set and str(ev.id) not in found:
                            found[str(ev.id)] = ev
                except Exception as e:
                    logger.warning(f"Error parsing evidence_json: {e}")
            return list(found.values())

    # ─────────────────────────────────────────────
    # Hook Options
    # ─────────────────────────────────────────────
    def save_hook_options(self, token: str, script_id: str, script_version: int, options: List[dict]):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hook_options
                (token, script_id, script_version, options_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (token, script_id, script_version, json.dumps(options, ensure_ascii=False), now_iso))
            conn.commit()

    def get_hook_options(self, token: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hook_options WHERE token = ?", (token,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "token": row["token"],
                "script_id": row["script_id"],
                "script_version": row["script_version"],
                "options": json.loads(row["options_json"]),
                "created_at": row["created_at"],
            }

    # ─────────────────────────────────────────────
    # Subscription Operations
    # ─────────────────────────────────────────────
    def set_subscription(self, user_key: UserKey, is_active: bool):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO subscriptions
                (chat_id, user_id, is_active, subscribed_at)
                VALUES (?, ?, ?, ?)
            """, (user_key.chat_id, user_key.user_id, 1 if is_active else 0, now_iso))
            conn.commit()

    def is_subscribed(self, user_key: UserKey) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT is_active FROM subscriptions WHERE chat_id = ? AND user_id = ?
            """, (user_key.chat_id, user_key.user_id))
            row = cursor.fetchone()
            return bool(row and row["is_active"])

    def get_active_subscribers(self) -> List[UserKey]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, user_id FROM subscriptions WHERE is_active = 1")
            return [UserKey(row["chat_id"], row["user_id"]) for row in cursor.fetchall()]

default_storage = Storage()

