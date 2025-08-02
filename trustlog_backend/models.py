# trustlog_backend/models.py

from flask_login import UserMixin
from trustlog_backend.database import get_db_connection # Absolute import

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        user_data = conn.execute("SELECT id, username, password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['password_hash'])
        return None

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        user_data = conn.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['password_hash'])
        return None