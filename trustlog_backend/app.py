# app.py
from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
from datetime import datetime
import json
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
DATABASE = 'tracking_log.db'
UPLOAD_FOLDER = 'uploads'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 Megabytes

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}

app.config['JSON_AS_ASCII'] = False

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")

CORS(app)

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
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
                impact_types TEXT NOT NULL, -- Storing as JSON array for multi-select
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_date ON log_records (date_of_incident);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_category ON log_records (category);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attachment_log_id ON attachments (log_record_id);')
        conn.commit()
    print("Database initialized or already exists.")

with app.app_context():
    init_db()

@app.route('/')
def home():
    """Basic home route to confirm the backend is running."""
    return "Welcome to the TrustLog Backend! API is available at /api/log_records"

@app.route('/api/log_records', methods=['POST'])
def create_log_record():
    """API endpoint to create a new log record."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    required_fields = ['date_of_incident', 'category', 'description_of_incident', 'impact_types']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing or empty required field: {field}"}), 400

    impact_types = data.get('impact_types')
    if not isinstance(impact_types, list):
        return jsonify({"error": "impact_types must be a list"}), 400
    impact_types_json = json.dumps(impact_types)

    date_of_incident = data.get('date_of_incident')
    time_of_incident = data.get('time_of_incident', None)
    category = data.get('category')
    description_of_incident = data.get('description_of_incident')
    impact_details = data.get('impact_details', None)
    supporting_evidence_snippet = data.get('supporting_evidence_snippet', None)
    exhibit_reference = data.get('exhibit_reference', None)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO log_records (
                date_of_incident, time_of_incident, category, description_of_incident,
                impact_types, impact_details, supporting_evidence_snippet, exhibit_reference
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                date_of_incident, time_of_incident, category, description_of_incident,
                impact_types_json, impact_details, supporting_evidence_snippet, exhibit_reference
            )
        )
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return jsonify({"message": "Log record created successfully", "id": log_id}), 201
    except sqlite3.Error as e:
        print(f"Database error during log record creation: {e}")
        return jsonify({"error": "Could not create log record", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during log record creation: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/log_records', methods=['GET'])
def get_log_records():
    """
    API endpoint to retrieve log records with optional filtering and sorting.
    Query parameters:
    - category: Filter by incident category.
    - start_date: Filter by date_of_incident >= start_date (YYYY-MM-DD).
    - end_date: Filter by date_of_incident <= end_date (YYYY-MM-DD).
    - sort_by: Column to sort by (e.g., 'date_of_incident', 'category').
    - sort_order: 'asc' or 'desc'.
    """
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

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        log_records = cursor.fetchall()
        conn.close()

        records_list = []
        for record in log_records:
            record_dict = dict(record)
            if record_dict['impact_types']:
                record_dict['impact_types'] = json.loads(record_dict['impact_types'])
            else:
                record_dict['impact_types'] = []
            records_list.append(record_dict)

        return jsonify(records_list), 200
    except sqlite3.Error as e:
        print(f"Database error during log record retrieval: {e}")
        return jsonify({"error": "Could not retrieve log records", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during log record retrieval: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/log_records/<int:log_id>', methods=['GET'])
def get_log_record_by_id(log_id):
    """API endpoint to retrieve a single log record by its ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM log_records WHERE id = ?", (log_id,))
        record = cursor.fetchone()
        conn.close()

        if record is None:
            return jsonify({"error": "Log record not found"}), 404

        record_dict = dict(record)
        if record_dict['impact_types']:
            record_dict['impact_types'] = json.loads(record_dict['impact_types'])
        else:
            record_dict['impact_types'] = []

        return jsonify(record_dict), 200
    except sqlite3.Error as e:
        print(f"Database error during single log record retrieval: {e}")
        return jsonify({"error": "Could not retrieve log record", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during single log record retrieval: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/log_records/<int:log_id>', methods=['PUT'])
def update_log_record(log_id):
    """API endpoint to update an existing log record."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    required_fields = ['date_of_incident', 'category', 'description_of_incident', 'impact_types']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing or empty required field: {field}"}), 400

    impact_types = data.get('impact_types')
    if not isinstance(impact_types, list):
        return jsonify({"error": "impact_types must be a list"}), 400
    impact_types_json = json.dumps(impact_types)

    date_of_incident = data.get('date_of_incident')
    time_of_incident = data.get('time_of_incident', None)
    category = data.get('category')
    description_of_incident = data.get('description_of_incident')
    impact_details = data.get('impact_details', None)
    supporting_evidence_snippet = data.get('supporting_evidence_snippet', None)
    exhibit_reference = data.get('exhibit_reference', None)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM log_records WHERE id = ?", (log_id,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"error": "Log record not found"}), 404

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
                impact_types_json, impact_details, supporting_evidence_snippet, exhibit_reference,
                log_id
            )
        )
        conn.commit()
        conn.close()
        if cursor.rowcount == 0:
             return jsonify({"message": "Log record found but no changes applied (data was identical)"}), 200
        return jsonify({"message": f"Log record {log_id} updated successfully"}), 200
    except sqlite3.Error as e:
        print(f"Database error during log record update: {e}")
        return jsonify({"error": "Could not update log record", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during log record update: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/log_records/<int:log_id>', methods=['DELETE'])
def delete_log_record(log_id):
    """API endpoint to delete a log record and its associated attachments."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Start a transaction for atomicity
        conn.execute('BEGIN TRANSACTION;')

        # 1. Get associated attachments to delete from disk
        attachments_to_delete = conn.execute("SELECT filepath, stored_filename FROM attachments WHERE log_record_id = ?", (log_id,)).fetchall()

        # 2. Delete attachment records from the database
        cursor.execute("DELETE FROM attachments WHERE log_record_id = ?", (log_id,))

        # 3. Delete the log record itself
        cursor.execute("DELETE FROM log_records WHERE id = ?", (log_id,))

        if cursor.rowcount == 0:
            conn.execute('ROLLBACK;')
            conn.close()
            return jsonify({"error": "Log record not found"}), 404

        conn.commit()

        # 4. Delete physical files from disk (after DB transaction is complete)
        for att in attachments_to_delete:
            full_filepath = os.path.join(UPLOAD_FOLDER, att['filepath'])
            if os.path.exists(full_filepath):
                try:
                    os.remove(full_filepath)
                    # Attempt to remove the parent directory if it becomes empty
                    # This helps keep the uploads folder clean (e.g., remove '2025/07' if empty)
                    parent_dir = os.path.dirname(full_filepath)
                    if not os.listdir(parent_dir): # Check if directory is empty
                        os.rmdir(parent_dir)
                        print(f"Removed empty directory: {parent_dir}")
                        # Also check the year directory if that became empty
                        year_dir = os.path.dirname(parent_dir)
                        if year_dir != UPLOAD_FOLDER and not os.listdir(year_dir):
                            os.rmdir(year_dir)
                            print(f"Removed empty year directory: {year_dir}")
                except OSError as e:
                    print(f"Error deleting file or directory {full_filepath}: {e}")


        conn.close()
        return jsonify({"message": f"Log record {log_id} and its attachments deleted successfully"}), 200

    except sqlite3.Error as e:
        conn.execute('ROLLBACK;')
        print(f"Database error during log record deletion: {e}")
        return jsonify({"error": "Could not delete log record", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during log record deletion: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@app.route('/api/attachments', methods=['POST'])
def upload_attachment():
    """
    API endpoint to handle file uploads.
    Expects FormData with 'file' and 'log_record_id'.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    if 'log_record_id' not in request.form:
        return jsonify({"error": "No log_record_id provided"}), 400

    file = request.files['file']
    log_record_id_str = request.form['log_record_id']

    try:
        log_record_id = int(log_record_id_str)
    except ValueError:
        return jsonify({"error": "Invalid log_record_id, must be an integer"}), 400

    conn_check = get_db_connection()
    record_exists = conn_check.execute("SELECT 1 FROM log_records WHERE id = ?", (log_record_id,)).fetchone()
    conn_check.close()
    if not record_exists:
        return jsonify({"error": f"Log record with ID {log_record_id} does not exist"}), 404

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        original_filename = file.filename
        secured_filename = secure_filename(original_filename)

        file_extension = secured_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        today_path = datetime.now().strftime("%Y/%m")
        destination_dir = os.path.join(UPLOAD_FOLDER, today_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)

        full_filepath = os.path.join(destination_dir, unique_filename)

        try:
            file.save(full_filepath)
            filesize_bytes = os.path.getsize(full_filepath)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO attachments (
                    log_record_id, filename, stored_filename, filepath, filetype, filesize_bytes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log_record_id, original_filename, unique_filename,
                    os.path.join(today_path, unique_filename),
                    file.content_type, filesize_bytes
                )
            )
            conn.commit()
            attachment_id = cursor.lastrowid
            conn.close()

            return jsonify({
                "message": "Attachment uploaded successfully",
                "attachment_id": attachment_id,
                "original_filename": original_filename,
                "stored_filename": unique_filename,
                "filepath": os.path.join(today_path, unique_filename),
                "log_record_id": log_record_id
            }), 201

        except sqlite3.Error as e:
            print(f"Database error during attachment upload: {e}")
            if os.path.exists(full_filepath):
                os.remove(full_filepath)
            return jsonify({"error": "Could not save attachment metadata", "details": str(e)}), 500
        except Exception as e:
            print(f"An unexpected error occurred during attachment upload: {e}")
            if os.path.exists(full_filepath):
                os.remove(full_filepath)
            return jsonify({"error": "An unexpected error occurred during file upload", "details": str(e)}), 500
    else:
        return jsonify({"error": "File type not allowed or no file selected"}), 400

@app.route('/api/attachments/<filename_to_find>', methods=['GET'])
def download_attachment(filename_to_find):
    """
    API endpoint to serve a single attachment file, with correct download name.
    """
    conn = get_db_connection()
    attachment_info = conn.execute(
        "SELECT filename, stored_filename, filepath FROM attachments WHERE stored_filename = ?",
        (filename_to_find,)
    ).fetchone()
    conn.close()

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

@app.route('/api/attachments/<int:attachment_id>', methods=['DELETE'])
def delete_attachment(attachment_id):
    """API endpoint to delete an individual attachment and its physical file."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Start a transaction
        conn.execute('BEGIN TRANSACTION;')

        # 1. Get attachment info to delete physical file and potentially update log_record_id's attachment_count
        attachment_info = conn.execute("SELECT log_record_id, filepath, stored_filename FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        if attachment_info is None:
            conn.execute('ROLLBACK;')
            conn.close()
            return jsonify({"error": "Attachment not found"}), 404

        log_record_id = attachment_info['log_record_id']
        file_to_delete_path = attachment_info['filepath']
        stored_filename_to_delete = attachment_info['stored_filename']

        # 2. Delete attachment record from the database
        cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        if cursor.rowcount == 0: # Should not happen if attachment_info was found, but good check
            conn.execute('ROLLBACK;')
            conn.close()
            return jsonify({"error": "Attachment not found during deletion attempt"}), 404

        conn.commit() # Commit DB changes

        # 3. Delete physical file from disk (after DB transaction is complete)
        full_filepath = os.path.join(UPLOAD_FOLDER, file_to_delete_path)
        if os.path.exists(full_filepath):
            try:
                os.remove(full_filepath)
                print(f"Deleted physical attachment file: {full_filepath}")
                # Attempt to remove empty parent directories (month/year)
                parent_dir = os.path.dirname(full_filepath)
                if not os.listdir(parent_dir): # Check if month directory is empty
                    os.rmdir(parent_dir)
                    print(f"Removed empty directory: {parent_dir}")
                    year_dir = os.path.dirname(parent_dir)
                    if year_dir != UPLOAD_FOLDER and not os.listdir(year_dir): # Check if year directory is empty
                        os.rmdir(year_dir)
                        print(f"Removed empty year directory: {year_dir}")
            except OSError as e:
                print(f"Error deleting physical file or directory {full_filepath}: {e}")
                # Log error but don't return 500, as DB is consistent

        conn.close()
        return jsonify({"message": f"Attachment {stored_filename_to_delete} deleted successfully"}), 200

    except sqlite3.Error as e:
        conn.execute('ROLLBACK;')
        print(f"Database error during attachment deletion: {e}")
        return jsonify({"error": "Could not delete attachment", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during attachment deletion: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@app.route('/api/log_records/<int:log_record_id>/attachments', methods=['GET'])
def get_log_record_attachments(log_record_id):
    """API endpoint to retrieve attachments for a specific log record."""
    try:
        conn = get_db_connection()
        attachments = conn.execute("SELECT * FROM attachments WHERE log_record_id = ?", (log_record_id,)).fetchall()
        conn.close()

        attachments_list = [dict(att) for att in attachments]
        return jsonify(attachments_list), 200
    except sqlite3.Error as e:
        print(f"Database error fetching attachments: {e}")
        return jsonify({"error": "Could not retrieve attachments", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred fetching attachments: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/config/allowed_extensions', methods=['GET'])
def get_allowed_extensions():
    """API endpoint to retrieve the list of allowed file extensions for uploads."""
    return jsonify(list(ALLOWED_EXTENSIONS)), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')