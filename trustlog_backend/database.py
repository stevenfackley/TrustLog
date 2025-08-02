# trustlog_backend/database.py

import sqlite3
import os
from trustlog_backend.config import Config # Absolute import

DATABASE_PATH = Config.DATABASE

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn

def init_db():
    """Initializes the database by creating tables if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_of_incident TEXT NOT NULL,
                time_of_incident TEXT,
                category TEXT NOT NULL,
                description_of_incident TEXT NOT NULL,
                impact_types TEXT NOT NULL,
                impact_details TEXT,
                supporting_evidence_snippet TEXT,
                exhibit_reference TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_record_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                filetype TEXT NOT NULL,
                filesize_bytes INTEGER NOT NULL,
                upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (log_record_id) REFERENCES log_records(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_date ON log_records (date_of_incident);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_category ON log_records (category);')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_user_username ON users (username);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attachment_log_id ON attachments (log_record_id);') # Ensure this index is also present
        conn.commit()
    print("Database initialized or already exists.")