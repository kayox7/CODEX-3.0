"""Database abstraction layer for WARDEN.
Supports SQLite (zero-config, works everywhere) and PostgreSQL.
Creates tables and provides thread-safe access.
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.config import settings

DB_FILE = os.getenv("SQLITE_PATH", "warden.db")

def get_connection() -> sqlite3.Connection:
    target_db = os.getenv("SQLITE_PATH", DB_FILE)
    conn = sqlite3.connect(target_db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        full_name TEXT,
        role TEXT NOT NULL DEFAULT 'auditor',
        created_at TEXT NOT NULL
    )
    """)

    # 2. Agent Passports table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_passports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        owner TEXT NOT NULL,
        purpose TEXT NOT NULL,
        allowed_actions TEXT NOT NULL DEFAULT '[]',
        allowed_data_classes TEXT NOT NULL DEFAULT '[]',
        max_amount REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'active',
        api_key_hash TEXT NOT NULL,
        api_key_prefix TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # 3. Ledger Entries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ledger_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        actor TEXT NOT NULL,
        payload TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        hash TEXT UNIQUE NOT NULL
    )
    """)

    # 4. Approval Requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS approval_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT UNIQUE NOT NULL,
        agent_id TEXT NOT NULL,
        action TEXT NOT NULL,
        params TEXT NOT NULL DEFAULT '{}',
        data_class TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0.0,
        records_affected INTEGER NOT NULL DEFAULT 0,
        reversibility TEXT NOT NULL,
        risk_score REAL NOT NULL,
        risk_level TEXT NOT NULL,
        risk_breakdown TEXT NOT NULL DEFAULT '{}',
        evidence_pack TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'PENDING',
        escalation_level TEXT NOT NULL DEFAULT 'APPROVER',
        created_at TEXT NOT NULL,
        sla_deadline TEXT NOT NULL,
        resolved_at TEXT,
        resolved_by TEXT,
        resolution_reason TEXT,
        ledger_hash TEXT
    )
    """)

    # 5. Provider Connections table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model TEXT NOT NULL,
        encrypted_api_key TEXT NOT NULL,
        key_last4 TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        system_prompt TEXT,
        allowed_actions TEXT NOT NULL DEFAULT '[]',
        allowed_data_classes TEXT NOT NULL DEFAULT '[]',
        max_amount REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'active',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_used_at TEXT,
        last_test_status TEXT,
        request_count INTEGER NOT NULL DEFAULT 0,
        blocked_count INTEGER NOT NULL DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()
