# trustlog_backend/config.py

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_super_secret_key_change_this_in_production_really'

    DATABASE = 'tracking_log.db'
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16 Megabytes
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created upload folder: {UPLOAD_FOLDER}")