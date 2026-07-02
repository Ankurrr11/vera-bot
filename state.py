"""
Persistent SQLite state store. Holds all context pushed by the judge.
Resilient to server restarts.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = "vera.db"

class StateStore:
    def __init__(self):
        self.started_at: datetime = datetime.utcnow()
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(DB_PATH)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            # Context table (for categories, merchants, customers, triggers)
            c.execute('''CREATE TABLE IF NOT EXISTS context 
                         (scope TEXT, context_id TEXT, version INTEGER, payload TEXT, 
                          stored_at TEXT, delivered_at TEXT,
                          PRIMARY KEY (scope, context_id))''')
            # Conversation history
            c.execute('''CREATE TABLE IF NOT EXISTS conversations
                         (conversation_id TEXT, role TEXT, body TEXT, ts TEXT)''')
            # Suppressions
            c.execute('''CREATE TABLE IF NOT EXISTS suppressions
                         (key TEXT PRIMARY KEY, ts TEXT)''')
            # Closed conversations
            c.execute('''CREATE TABLE IF NOT EXISTS closed_conversations
                         (conversation_id TEXT PRIMARY KEY)''')
            # Auto-reply counts
            c.execute('''CREATE TABLE IF NOT EXISTS auto_reply_counts
                         (merchant_id TEXT PRIMARY KEY, count INTEGER)''')
            # V2 Enterprise: Merchant Profiles
            c.execute('''CREATE TABLE IF NOT EXISTS merchant_profiles
                         (merchant_id TEXT PRIMARY KEY, profile_summary TEXT)''')
            # V2 Enterprise: CTA Analytics
            c.execute('''CREATE TABLE IF NOT EXISTS cta_analytics
                         (category_slug TEXT, cta_name TEXT, attempts INTEGER, successes INTEGER,
                          PRIMARY KEY (category_slug, cta_name))''')
            # Mapping conversation to trigger
            c.execute('''CREATE TABLE IF NOT EXISTS conversation_to_trigger
                         (conversation_id TEXT PRIMARY KEY, trigger_id TEXT)''')
            # V2 Enterprise: Tool Executions
            c.execute('''CREATE TABLE IF NOT EXISTS tool_executions
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, tool_name TEXT, tool_args TEXT, ts TEXT)''')
            conn.commit()

    def set_conversation_trigger(self, conversation_id: str, trigger_id: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("REPLACE INTO conversation_to_trigger (conversation_id, trigger_id) VALUES (?, ?)", (conversation_id, trigger_id))
            conn.commit()

    def get_conversation_trigger_id(self, conversation_id: str) -> Optional[str]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT trigger_id FROM conversation_to_trigger WHERE conversation_id=?", (conversation_id,))
            row = c.fetchone()
            return row[0] if row else None

    def store_context(self, scope: str, context_id: str, version: int, payload: dict, delivered_at: str) -> dict:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT version, stored_at FROM context WHERE scope=? AND context_id=?", (scope, context_id))
            row = c.fetchone()
            if row:
                existing_version, existing_stored_at = row
                if existing_version == version:
                    return {"accepted": True, "ack_id": f"ack_{context_id}_v{version}_noop", "stored_at": existing_stored_at}
                if existing_version > version:
                    return {"accepted": False, "reason": "stale_version", "current_version": existing_version}
            
            stored_at = datetime.utcnow().isoformat() + "Z"
            c.execute("REPLACE INTO context (scope, context_id, version, payload, stored_at, delivered_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (scope, context_id, version, json.dumps(payload), stored_at, delivered_at))
            conn.commit()
            return {"accepted": True, "ack_id": f"ack_{context_id}_v{version}", "stored_at": stored_at}

    def _get_entry(self, scope: str, context_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT version, payload, stored_at, delivered_at FROM context WHERE scope=? AND context_id=?", (scope, context_id))
            row = c.fetchone()
            if row:
                return {"version": row[0], "payload": json.loads(row[1]), "stored_at": row[2], "delivered_at": row[3]}
        return None

    def get_context(self, scope: str, context_id: str) -> Optional[dict]:
        entry = self._get_entry(scope, context_id)
        return entry["payload"] if entry else None
        
    def get_category(self, slug: str): return self._get_entry("category", slug)
    def get_merchant(self, merchant_id: str): return self._get_entry("merchant", merchant_id)
    def get_customer(self, customer_id: str): return self._get_entry("customer", customer_id)
    def get_trigger(self, trigger_id: str): return self._get_entry("trigger", trigger_id)

    def add_conversation_turn(self, conversation_id: str, role: str, body: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            ts = datetime.utcnow().isoformat() + "Z"
            c.execute("INSERT INTO conversations (conversation_id, role, body, ts) VALUES (?, ?, ?, ?)", 
                      (conversation_id, role, body, ts))
            conn.commit()

    def get_conversation(self, conversation_id: str) -> list:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT role, body, ts FROM conversations WHERE conversation_id=? ORDER BY ts ASC", (conversation_id,))
            return [{"role": r[0], "body": r[1], "ts": r[2]} for r in c.fetchall()]

    def suppress(self, key: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            ts = datetime.utcnow().isoformat() + "Z"
            c.execute("REPLACE INTO suppressions (key, ts) VALUES (?, ?)", (key, ts))
            conn.commit()

    def is_suppressed(self, key: str) -> bool:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM suppressions WHERE key=?", (key,))
            return c.fetchone() is not None

    def close_conversation(self, conversation_id: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("REPLACE INTO closed_conversations (conversation_id) VALUES (?)", (conversation_id,))
            conn.commit()

    def is_closed(self, conversation_id: str) -> bool:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM closed_conversations WHERE conversation_id=?", (conversation_id,))
            return c.fetchone() is not None
            
    def get_auto_reply_count(self, merchant_id: str) -> int:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT count FROM auto_reply_counts WHERE merchant_id=?", (merchant_id,))
            row = c.fetchone()
            return row[0] if row else 0
            
    def set_auto_reply_count(self, merchant_id: str, count: int):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("REPLACE INTO auto_reply_counts (merchant_id, count) VALUES (?, ?)", (merchant_id, count))
            conn.commit()

    def get_counts(self) -> dict:
        with self._get_conn() as conn:
            c = conn.cursor()
            counts = {}
            for scope in ["category", "merchant", "customer", "trigger"]:
                c.execute("SELECT COUNT(*) FROM context WHERE scope=?", (scope,))
                counts[scope] = c.fetchone()[0]
            return counts

    def uptime_seconds(self) -> int:
        return int((datetime.utcnow() - self.started_at).total_seconds())

    # --- V2 Enterprise Methods ---
    
    def get_merchant_profile(self, merchant_id: str) -> str:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT profile_summary FROM merchant_profiles WHERE merchant_id=?", (merchant_id,))
            row = c.fetchone()
            return row[0] if row else ""

    def set_merchant_profile(self, merchant_id: str, profile_summary: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("REPLACE INTO merchant_profiles (merchant_id, profile_summary) VALUES (?, ?)", (merchant_id, profile_summary))
            conn.commit()

    def record_cta_attempt(self, category_slug: str, cta_name: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO cta_analytics (category_slug, cta_name, attempts, successes) VALUES (?, ?, 1, 0) ON CONFLICT(category_slug, cta_name) DO UPDATE SET attempts=attempts+1", (category_slug, cta_name))
            conn.commit()

    def record_cta_success(self, category_slug: str, cta_name: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("UPDATE cta_analytics SET successes=successes+1 WHERE category_slug=? AND cta_name=?", (category_slug, cta_name))
            conn.commit()

    def get_top_ctas(self, category_slug: str, limit: int = 3) -> list:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT cta_name, attempts, successes FROM cta_analytics WHERE category_slug=? ORDER BY successes DESC, attempts DESC LIMIT ?", (category_slug, limit))
            return [{"cta_name": r[0], "attempts": r[1], "successes": r[2]} for r in c.fetchall()]

    def log_tool_execution(self, merchant_id: str, tool_name: str, tool_args: dict):
        with self._get_conn() as conn:
            c = conn.cursor()
            ts = datetime.utcnow().isoformat() + "Z"
            c.execute("INSERT INTO tool_executions (merchant_id, tool_name, tool_args, ts) VALUES (?, ?, ?, ?)", (merchant_id, tool_name, json.dumps(tool_args), ts))
            conn.commit()

    def get_recent_tool_executions(self, limit: int = 10) -> list:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT merchant_id, tool_name, tool_args, ts FROM tool_executions ORDER BY ts DESC LIMIT ?", (limit,))
            return [{"merchant_id": r[0], "tool_name": r[1], "tool_args": json.loads(r[2]), "ts": r[3]} for r in c.fetchall()]

store = StateStore()
