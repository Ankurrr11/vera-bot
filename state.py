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
            conn.commit()

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


store = StateStore()
