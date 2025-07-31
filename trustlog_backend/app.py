# app.py
from flask import Flask, request, jsonify, send_from_directory, session
import sqlite3
import os
from datetime import datetime
import json
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
DATABASE = 'tracking_log.db'
UPLOAD_FOLDER = 'uploads'

# Secret key for session management (CRITICAL for Flask-Login and session security)
# In production, this should be a strong, randomly generated string,
# loaded from an environment variable or config file, NOT hardcoded.
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this_in_production'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 Megabytes (adjust as needed)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}

app.config['JSON_AS_ASCII'] = False

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")

CORS(app, supports_credentials=True) # IMPORTANT: Enable supports_credentials for sessions/cookies

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Define the view Flask-Login should redirect to for login

# User class for Flask-Login
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

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Unauthorized: Please log in to access this resource"}), 401

# --- Database Connection and Initialization ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Create log_records table
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
        # Create attachments table
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
        # Create users table for authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_date ON log_records (date_of_incident);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_category ON log_records (category);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attachment_log_id ON attachments (log_record_id);')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_user_username ON users (username);')
        conn.commit()
    print("Database initialized or already exists.")

with app.app_context():
    init_db()

# Helper function for file extension validation (Moved to ensure global accessibility)
def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- API Routes ---
@app.route('/')
def home():
    return "Welcome to the TrustLog Backend!"

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns application status and user authentication status."""
    return jsonify({
        "message": "TrustLog Backend is running.",
        "authenticated": current_user.is_authenticated,
        "username": current_user.username if current_user.is_authenticated else None
    })

@app.route('/api/register', methods=['POST'])
def register():
    """Endpoint for user registration."""
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
        print(f"Database error during registration: {e}")
        return jsonify({"error": "Could not register user", "details": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint for user login."""
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

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Endpoint for user logout."""
    logout_user()
    return jsonify({"message": "Logged out successfully"}), 200

# --- Protected API Routes ---
# Modified create_log_record to handle combined form data and files

@app.route('/api/log_records', methods=['POST'])
@login_required
def create_log_record():
    """
    API endpoint to create a new log record and handle attachments atomically.
    Expects FormData with text fields and file parts.
    """
    conn = None
    temp_saved_files = [] # Keep track of files saved to disk for cleanup on rollback

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.execute('BEGIN TRANSACTION;') # Start a transaction

        # Parse form data
        data = request.form
        files = request.files.getlist('files') # Get list of all files with 'files' field name

        # Server-side validation for mandatory text fields
        required_fields = ['date_of_incident', 'category', 'description_of_incident', 'impact_types']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing or empty required field: {field}")

        # Parse impact_types from JSON string (sent by FormData)
        impact_types_json_str = data.get('impact_types')
        try:
            impact_types = json.loads(impact_types_json_str) if impact_types_json_str else []
            if not isinstance(impact_types, list):
                raise ValueError("impact_types must be a valid JSON array")
        except json.JSONDecodeError:
            raise ValueError("impact_types must be a valid JSON array string")

        date_of_incident = data.get('date_of_incident')
        time_of_incident = data.get('time_of_incident', None)
        category = data.get('category')
        description_of_incident = data.get('description_of_incident')
        impact_details = data.get('impact_details', None)
        supporting_evidence_snippet = data.get('supporting_evidence_snippet', None)
        if supporting_evidence_snippet == 'null':
            supporting_evidence_snippet = None
        exhibit_reference = data.get('exhibit_reference', None)

        # Insert log record
        cursor.execute(
            """
            INSERT INTO log_records (
                date_of_incident, time_of_incident, category, description_of_incident,
                impact_types, impact_details, supporting_evidence_snippet, exhibit_reference
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                date_of_incident, time_of_incident, category, description_of_incident,
                json.dumps(impact_types), impact_details, supporting_evidence_snippet, exhibit_reference
            )
        )
        log_id = cursor.lastrowid

        # Handle file uploads if any
        for file in files:
            if file.filename == '':
                continue

            if not allowed_file(file.filename): # Use allowed_file helper
                raise ValueError(f"File type not allowed for: {file.filename}")

            original_filename = file.filename
            secured_filename = secure_filename(original_filename)
            file_extension = secured_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_extension}"

            today_path = datetime.now().strftime("%Y/%m")
            destination_dir = os.path.join(UPLOAD_FOLDER, today_path)
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)

            full_filepath_on_disk = os.path.join(destination_dir, unique_filename)
            
            file.save(full_filepath_on_disk) # Save physical file
            temp_saved_files.append(full_filepath_on_disk) # Add to cleanup list

            filesize_bytes = os.path.getsize(full_filepath_on_disk)

            # Insert attachment metadata
            cursor.execute(
                """
                INSERT INTO attachments (
                    log_record_id, filename, stored_filename, filepath, filetype, filesize_bytes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id, original_filename, unique_filename,
                    os.path.join(today_path, unique_filename), # Store relative path
                    file.content_type, filesize_bytes
                )
            )

        conn.commit() # Commit transaction if everything successful
        return jsonify({"message": "Log record and attachments created successfully", "id": log_id}), 201

    except (ValueError, sqlite3.Error) as e:
        if conn: conn.execute('ROLLBACK;') # Rollback DB transaction on error
        for fpath in temp_saved_files: # Clean up physical files
            if os.path.exists(fpath):
                os.remove(fpath)
        print(f"Error during combined record/attachment creation: {e}")
        return jsonify({"error": str(e)}), 400 if isinstance(e, ValueError) else 500
    except Exception as e:
        if conn: conn.execute('ROLLBACK;') # Rollback DB transaction on error
        for fpath in temp_saved_files: # Clean up physical files
            if os.path.exists(fpath):
                os.remove(fpath)
        print(f"An unexpected error occurred during combined record/attachment creation: {e}")
        return jsonify({"error": "An unexpected server error occurred during record creation", "details": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/log_records', methods=['GET'])
@login_required
def get_log_records():
    conn = None
    try:
        conn = get_db_connection()
        category_filter = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        sort_by = request.args.get('sort_by', 'date_of_incident')
        sort_order = request.args.get('sort_order', 'desc').upper()

        valid_sort_columns = ['date_of_incident', 'category', 'created_at']
        if sort_by not in valid_sort_columns:
            return jsonify({"error": f"Invalid sort_by column: {sort_by}"}), 400

        if sort_order not in ['ASC', 'DESC']:
            return jsonify({"error": f"Invalid sort_order: {sort_order}"}), 400

        query = """
            SELECT lr.*, COUNT(a.id) AS attachment_count
            FROM log_records lr
            LEFT JOIN attachments a ON lr.id = a.log_record_id
            WHERE 1=1
        """
        params = []

        if category_filter:
            query += " AND lr.category = ?"
            params.append(category_filter)

        if start_date:
            query += " AND lr.date_of_incident >= ?"
            params.append(start_date)

        if end_date:
            query += " AND lr.date_of_incident <= ?"
            params.append(end_date)

        query += f" GROUP BY lr.id ORDER BY lr.{sort_by} {sort_order}, lr.created_at DESC"

        cursor = conn.cursor()
        cursor.execute(query, params)
        log_records = cursor.fetchall()

        records_list = []
        for record in log_records:
            record_dict = dict(record)
            if record_dict['impact_types']:
                record_dict['impact_types'] = json.loads(record_dict['impact_types'])
            else:
                record_dict['impact_types'] = []
            records_list.append(record_dict)

        return jsonify(records_list), 200
    except Exception as e:
        print(f"An unexpected error occurred during log record retrieval: {e}")
        return jsonify({"error": "An unexpected server error occurred during record retrieval", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/log_records/<int:log_id>', methods=['GET'])
@login_required
def get_log_record_by_id(log_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM log_records WHERE id = ?", (log_id,))
        record = cursor.fetchone()

        if record is None:
            return jsonify({"error": "Log record not found"}), 404

        record_dict = dict(record)
        if record_dict['impact_types']:
            record_dict['impact_types'] = json.loads(record_dict['impact_types'])
        else:
            record_dict['impact_types'] = []

        return jsonify(record_dict), 200
    except Exception as e:
        print(f"An unexpected error occurred during single log record retrieval: {e}")
        return jsonify({"error": "An unexpected server error occurred during record retrieval", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/log_records/<int:log_id>', methods=['PUT'])
@login_required
def update_log_record(log_id):
    """
    API endpoint to update an existing log record.
    Expects FormData with text fields and new file parts.
    Existing attachments are managed via separate DELETE attachment endpoint.
    """
    conn = None
    temp_saved_files = [] # For cleanup on rollback

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.execute('BEGIN TRANSACTION;') # Start a transaction

        # Check if log record exists
        cursor.execute("SELECT id FROM log_records WHERE id = ?", (log_id,))
        if cursor.fetchone() is None:
            conn.execute('ROLLBACK;')
            return jsonify({"error": "Log record not found"}), 404

        # Parse form data
        data = request.form
        new_files = request.files.getlist('files')

        # Server-side validation for mandatory text fields
        required_fields = ['date_of_incident', 'category', 'description_of_incident', 'impact_types']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing or empty required field: {field}")

        # Parse impact_types from JSON string
        impact_types_json_str = data.get('impact_types')
        try:
            impact_types = json.loads(impact_types_json_str) if impact_types_json_str else []
            if not isinstance(impact_types, list):
                raise ValueError("impact_types must be a valid JSON array")
        except json.JSONDecodeError:
            raise ValueError("impact_types must be a valid JSON array string")

        date_of_incident = data.get('date_of_incident')
        time_of_incident = data.get('time_of_incident', None)
        category = data.get('category')
        description_of_incident = data.get('description_of_incident')
        impact_details = data.get('impact_details', None)
        supporting_evidence_snippet = data.get('supporting_evidence_snippet', None)
        if supporting_evidence_snippet == 'null':
            supporting_evidence_snippet = None
        exhibit_reference = data.get('exhibit_reference', None)

        # Update log record
        cursor.execute(
            """
            UPDATE log_records SET
                date_of_incident = ?,
                time_of_incident = ?,
                category = ?,
                description_of_incident = ?,
                impact_types = ?,
                impact_details = ?,
                supporting_evidence_snippet = ?,
                exhibit_reference = ?
            WHERE id = ?
            """,
            (
                date_of_incident, time_of_incident, category, description_of_incident,
                json.dumps(impact_types), impact_details, supporting_evidence_snippet, exhibit_reference,
                log_id
            )
        )

        # Handle new file uploads for this updated record
        for file in new_files:
            if file.filename == '':
                continue

            if not allowed_file(file.filename):
                raise ValueError(f"File type not allowed for new attachment: {file.filename}")

            original_filename = file.filename
            secured_filename = secure_filename(original_filename)
            file_extension = secured_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_extension}"

            today_path = datetime.now().strftime("%Y/%m")
            destination_dir = os.path.join(UPLOAD_FOLDER, today_path)
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)

            full_filepath_on_disk = os.path.join(destination_dir, unique_filename)
            
            file.save(full_filepath_on_disk)
            temp_saved_files.append(full_filepath_on_disk)

            filesize_bytes = os.path.getsize(full_filepath_on_disk)

            cursor.execute(
                """
                INSERT INTO attachments (
                    log_record_id, filename, stored_filename, filepath, filetype, filesize_bytes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id, original_filename, unique_filename,
                    os.path.join(today_path, unique_filename),
                    file.content_type, filesize_bytes
                )
            )
        
        conn.commit()
        return jsonify({"message": f"Log record {log_id} updated and new attachments added successfully"}), 200

    except (ValueError, sqlite3.Error) as e:
        if conn: conn.execute('ROLLBACK;')
        for fpath in temp_saved_files:
            if os.path.exists(fpath):
                os.remove(fpath)
        print(f"Error during record update/attachment add: {e}")
        return jsonify({"error": str(e)}), 400 if isinstance(e, ValueError) else 500
    except Exception as e:
        if conn: conn.execute('ROLLBACK;')
        for fpath in temp_saved_files:
            if os.path.exists(fpath):
                os.remove(fpath)
        print(f"An unexpected error occurred during record update/attachment add: {e}")
        return jsonify({"error": "An unexpected server error occurred during record update", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/log_records/<int:log_id>', methods=['DELETE'])
@login_required
def delete_log_record(log_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        conn.execute('BEGIN TRANSACTION;')

        attachments_to_delete = conn.execute("SELECT filepath, stored_filename FROM attachments WHERE log_record_id = ?", (log_id,)).fetchall()

        cursor.execute("DELETE FROM attachments WHERE log_record_id = ?", (log_id,))

        cursor.execute("DELETE FROM log_records WHERE id = ?", (log_id,))

        if cursor.rowcount == 0:
            conn.execute('ROLLBACK;')
            return jsonify({"error": "Log record not found"}), 404

        conn.commit()

        for att in attachments_to_delete:
            full_filepath = os.path.join(UPLOAD_FOLDER, att['filepath'])
            if os.path.exists(full_filepath):
                try:
                    os.remove(full_filepath)
                    print(f"Deleted file: {full_filepath}")
                    parent_dir = os.path.dirname(full_filepath)
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        print(f"Removed empty directory: {parent_dir}")
                        year_dir = os.path.dirname(parent_dir)
                        if os.path.exists(year_dir) and year_dir != UPLOAD_FOLDER and not os.listdir(year_dir):
                            os.rmdir(year_dir)
                            print(f"Removed empty year directory: {year_dir}")
                except OSError as e:
                    print(f"Error deleting file or directory {full_filepath}: {e}")

        return jsonify({"message": f"Log record {log_id} and its attachments deleted successfully"}), 200

    except Exception as e:
        if conn: conn.execute('ROLLBACK;')
        print(f"An unexpected error occurred during log record deletion: {e}")
        return jsonify({"error": "An unexpected server error occurred during record deletion", "details": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/attachments/<filename_to_find>', methods=['GET'])
def download_attachment(filename_to_find):
    conn = None
    try:
        conn = get_db_connection()
        attachment_info = conn.execute(
            "SELECT filename, stored_filename, filepath FROM attachments WHERE stored_filename = ?",
            (filename_to_find,)
        ).fetchone()

        if attachment_info:
            original_filename = attachment_info['filename']
            stored_filename = attachment_info['stored_filename']
            relative_dir = os.path.dirname(attachment_info['filepath'])
            full_directory_to_serve_from = os.path.join(UPLOAD_FOLDER, relative_dir)

            return send_from_directory(
                full_directory_to_serve_from,
                stored_filename,
                as_attachment=True,
                download_name=original_filename
            )
        else:
            return jsonify({"error": "File not found or not permitted"}), 404
    except Exception as e:
        print(f"Error serving attachment: {e}")
        return jsonify({"error": "Could not serve file"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/attachments/<int:attachment_id>', methods=['DELETE'])
@login_required
def delete_attachment(attachment_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        conn.execute('BEGIN TRANSACTION;')

        attachment_info = conn.execute("SELECT log_record_id, filepath, stored_filename FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        if attachment_info is None:
            conn.execute('ROLLBACK;')
            return jsonify({"error": "Attachment not found"}), 404

        log_record_id = attachment_info['log_record_id']
        file_to_delete_path = attachment_info['filepath']
        stored_filename_to_delete = attachment_info['stored_filename']

        cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        if cursor.rowcount == 0:
            conn.execute('ROLLBACK;')
            return jsonify({"error": "Attachment not found during deletion attempt"}), 404

        conn.commit()

        full_filepath = os.path.join(UPLOAD_FOLDER, file_to_delete_path)
        if os.path.exists(full_filepath):
            try:
                os.remove(full_filepath)
                print(f"Deleted physical attachment file: {full_filepath}")
                parent_dir = os.path.dirname(full_filepath)
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                    print(f"Removed empty directory: {parent_dir}")
                    year_dir = os.path.dirname(parent_dir)
                    if os.path.exists(year_dir) and year_dir != UPLOAD_FOLDER and not os.listdir(year_dir):
                        os.rmdir(year_dir)
                        print(f"Removed empty year directory: {year_dir}")
            except OSError as e:
                print(f"Error deleting file or directory {full_filepath}: {e}")

        return jsonify({"message": f"Attachment {stored_filename_to_delete} deleted successfully"}), 200

    except Exception as e:
        if conn: conn.execute('ROLLBACK;')
        print(f"An unexpected error occurred during attachment deletion: {e}")
        return jsonify({"error": "An unexpected server error occurred during attachment deletion", "details": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/log_records/<int:log_record_id>/attachments', methods=['GET'])
@login_required
def get_log_record_attachments(log_record_id):
    conn = None
    try:
        conn = get_db_connection()
        attachments = conn.execute("SELECT * FROM attachments WHERE log_record_id = ?", (log_record_id,)).fetchall()

        attachments_list = [dict(att) for att in attachments]
        return jsonify(attachments_list), 200
    except Exception as e:
        print(f"An unexpected error occurred fetching attachments: {e}")
        return jsonify({"error": "An unexpected server error occurred fetching attachments", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/config/allowed_extensions', methods=['GET'])
@login_required
def get_allowed_extensions():
    return jsonify(list(ALLOWED_EXTENSIONS)), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')