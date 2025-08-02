# trustlog_backend/auth.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from trustlog_backend.database import get_db_connection
from trustlog_backend.models import User
from trustlog_backend.config import Config # Import Config to access ALLOWED_EXTENSIONS

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db_connection()
    existing_user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing_user:
        conn.close()
        return jsonify({"error": "Username already exists"}), 409

    hashed_password = generate_password_hash(password)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        new_user_id = cursor.lastrowid
        user = User.get(new_user_id)
        login_user(user)
        return jsonify({"message": "User registered and logged in successfully", "username": user.username}), 201
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error during registration: {e}")
        return jsonify({"error": "Could not register user", "details": str(e)}), 500
    finally:
        conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = User.get_by_username(username)
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        return jsonify({"message": "Logged in successfully", "username": user.username}), 200
    return jsonify({"error": "Invalid username or password"}), 401

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"}), 200

@auth_bp.route('/status', methods=['GET'])
def get_status():
    """Returns application status and user authentication status."""
    return jsonify({
        "message": "TrustLog Backend is running.",
        "authenticated": current_user.is_authenticated,
        "username": current_user.username if current_user.is_authenticated else None
    })

# NEW: Moved from logs.py
@auth_bp.route('/config/allowed_extensions', methods=['GET'])
def get_allowed_extensions():
    """API endpoint to retrieve the list of allowed file extensions for uploads."""
    # This endpoint is NOT login_required by design, so frontend can get types before login
    return jsonify(list(Config.ALLOWED_EXTENSIONS)), 200