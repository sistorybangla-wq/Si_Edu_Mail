"""
database.py - SQLite database management
"""

import sqlite3
from typing import Optional, Dict, List

class Database:
    def __init__(self, db_file="users.db"):
        self.db_file = db_file
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                status TEXT DEFAULT 'pending',
                balance REAL DEFAULT 0,
                emails_generated INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Emails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                password TEXT,
                student_id TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('price_per_email', '5')
        """)
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(self.db_file)
    
    def add_user(self, user_id, username=None, first_name=None, last_name=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, last_name))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    
    def get_user(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    
    def update_user_status(self, user_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE users SET status = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (status, user_id))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    
    def update_balance(self, user_id, amount):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE users SET balance = balance + ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (amount, user_id))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    
    def add_email(self, user_id, email, password, student_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO emails (user_id, email, password, student_id)
                VALUES (?, ?, ?, ?)
            """, (user_id, email, password, student_id))
            cursor.execute("""
                UPDATE users SET emails_generated = emails_generated + 1
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    
    def get_user_emails(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email, password, student_id, generated_at FROM emails
            WHERE user_id = ? ORDER BY generated_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"email": r[0], "password": r[1], "student_id": r[2], "generated_at": r[3]} for r in rows]
    
    def get_all_users(self, status=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("""
                SELECT user_id, username, first_name, status, balance, emails_generated, registered_at
                FROM users WHERE status = ? ORDER BY registered_at DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT user_id, username, first_name, status, balance, emails_generated, registered_at
                FROM users ORDER BY registered_at DESC
            """)
        rows = cursor.fetchall()
        conn.close()
        return [{"user_id": r[0], "username": r[1], "first_name": r[2], "status": r[3], "balance": r[4], "emails_generated": r[5], "registered_at": r[6]} for r in rows]
    
    def get_statistics(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'approved'")
        approved_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
        pending_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM emails")
        total_emails = cursor.fetchone()[0]
        cursor.execute("SELECT value FROM settings WHERE key = 'price_per_email'")
        price = cursor.fetchone()
        price = float(price[0]) if price else 5.0
        conn.close()
        return {
            "total_users": total_users,
            "approved_users": approved_users,
            "pending_users": pending_users,
            "total_emails": total_emails,
            "price_per_email": price
        }
    
    def get_setting(self, key):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    
    def set_setting(self, key, value):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()