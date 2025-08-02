# trustlog_backend/routes/logs.py

from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_login import login_required
import sqlite3
import os
import json
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename

# Corrected imports: Import Config class, not its attributes directly
from trustlog_backend.database import get_db_connection
from trustlog_backend.config import Config, UPLOAD_FOLDER # Keep UPLOAD_FOLDER as it's directly used in this file
from trustlog_backend.allowed_file import allowed_file # Corrected: Absolute import

logs_bp = Blueprint('logs', __name__)

@logs_bp.route('/', methods=['POST'])
@login_required
def create_log_record():
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
                # Raise ValueError to trigger rollback and custom error response
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
        if supporting_evidence_snippet == 'null': # Frontend might send "null" string
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
                continue # Skip empty file parts

            if not allowed_file(file.filename): # Use allowed_file helper
                raise ValueError(f"File type not allowed for: {file.filename}")

            original_filename = file.filename
            secured_filename = secure_filename(original_filename)
            file_extension = secured_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_extension}"

            today_path = datetime.now().strftime("%Y/%m")
            # Access UPLOAD_FOLDER from Config.UPLOAD_FOLDER
            destination_dir = os.path.join(Config.UPLOAD_FOLDER, today_path)
            # Ensure destination directory exists before saving
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
        current_app.logger.error(f"Error during combined record/attachment creation: {e}")
        # Return 400 for validation errors, 500 for DB errors
        return jsonify({"error": str(e)}), 400 if isinstance(e, ValueError) else 500
    except Exception as e:
        if conn: conn.execute('ROLLBACK;') # Rollback DB transaction on error
        for fpath in temp_saved_files: # Clean up physical files
            if os.path.exists(fpath):
                os.remove(fpath)
        current_app.logger.error(f"An unexpected error occurred during combined record/attachment creation: {e}")
        return jsonify({"error": "An unexpected server error occurred during record creation", "details": str(e)}), 500
    finally:
        if conn: conn.close()


@logs_bp.route('/', methods=['GET'])
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
        current_app.logger.error(f"An unexpected error occurred during log record retrieval: {e}")
        return jsonify({"error": "An unexpected server error occurred during record retrieval", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@logs_bp.route('/<int:log_id>', methods=['GET'])
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
        current_app.logger.error(f"An unexpected error occurred during single log record retrieval: {e}")
        return jsonify({"error": "An unexpected server error occurred during record retrieval", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@logs_bp.route('/<int:log_id>', methods=['PUT'])
@login_required
def update_log_record(log_id):
    conn = None
    temp_saved_files = [] # For cleanup on rollback

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.execute('BEGIN TRANSACTION;')

        cursor.execute("SELECT id FROM log_records WHERE id = ?", (log_id,))
        if cursor.fetchone() is None:
            conn.execute('ROLLBACK;')
            return jsonify({"error": "Log record not found"}), 404

        data = request.form
        new_files = request.files.getlist('files')

        required_fields = ['date_of_incident', 'category', 'description_of_incident', 'impact_types']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing or empty required field: {field}")

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
            destination_dir = os.path.join(Config.UPLOAD_FOLDER, today_path)
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
        current_app.logger.error(f"Error during record update/attachment add: {e}")
        return jsonify({"error": str(e)}), 400 if isinstance(e, ValueError) else 500
    except Exception as e:
        if conn: conn.execute('ROLLBACK;')
        for fpath in temp_saved_files:
            if os.path.exists(fpath):
                os.remove(fpath)
        current_app.logger.error(f"An unexpected error occurred during record update/attachment add: {e}")
        return jsonify({"error": "An unexpected server error occurred during record update", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@logs_bp.route('/<int:log_id>', methods=['DELETE'])
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
            full_filepath = os.path.join(Config.UPLOAD_FOLDER, att['filepath'])
            if os.path.exists(full_filepath):
                try:
                    os.remove(full_filepath)
                    current_app.logger.info(f"Deleted file: {full_filepath}")
                    parent_dir = os.path.dirname(full_filepath)
                    if os.path.exists(parent_dir) and parent_dir.startswith(Config.UPLOAD_FOLDER) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        current_app.logger.info(f"Removed empty directory: {parent_dir}")
                        year_dir = os.path.dirname(parent_dir)
                        if os.path.exists(year_dir) and year_dir.startswith(Config.UPLOAD_FOLDER) and year_dir != Config.UPLOAD_FOLDER and not os.listdir(year_dir):
                            os.rmdir(year_dir)
                            current_app.logger.info(f"Removed empty year directory: {year_dir}")
                except OSError as e:
                    current_app.logger.error(f"Error deleting file or directory {full_filepath}: {e}")

        return jsonify({"message": f"Log record {log_id} and its attachments deleted successfully"}), 200

    except Exception as e:
        if conn: conn.execute('ROLLBACK;')
        current_app.logger.error(f"An unexpected error occurred during log record deletion: {e}")
        return jsonify({"error": "An unexpected server error occurred during record deletion", "details": str(e)}), 500
    finally:
        if conn: conn.close()


@logs_bp.route('/attachments/<filename_to_find>', methods=['GET'])
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
            full_directory_to_serve_from = os.path.join(Config.UPLOAD_FOLDER, relative_dir)

            return send_from_directory(
                full_directory_to_serve_from,
                stored_filename,
                as_attachment=True,
                download_name=original_filename
            )
        else:
            return jsonify({"error": "File not found or not permitted"}), 404
    except Exception as e:
        current_app.logger.error(f"Error serving attachment: {e}")
        return jsonify({"error": "Could not serve file"}), 500
    finally:
        if conn: conn.close()

@logs_bp.route('/attachments/<int:attachment_id>', methods=['DELETE'])
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

        full_filepath = os.path.join(Config.UPLOAD_FOLDER, file_to_delete_path)
        if os.path.exists(full_filepath):
            try:
                os.remove(full_filepath)
                current_app.logger.info(f"Deleted physical attachment file: {full_filepath}")
                parent_dir = os.path.dirname(full_filepath)
                if os.path.exists(parent_dir) and parent_dir.startswith(Config.UPLOAD_FOLDER) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                    current_app.logger.info(f"Removed empty directory: {parent_dir}")
                    year_dir = os.path.dirname(parent_dir)
                    if os.path.exists(year_dir) and year_dir.startswith(Config.UPLOAD_FOLDER) and year_dir != Config.UPLOAD_FOLDER and not os.listdir(year_dir):
                        os.rmdir(year_dir)
                        current_app.logger.info(f"Removed empty year directory: {year_dir}")
            except OSError as e:
                current_app.logger.error(f"Error deleting file or directory {full_filepath}: {e}")

        return jsonify({"message": f"Attachment {stored_filename_to_delete} deleted successfully"}), 200

    except Exception as e:
        if conn: conn.execute('ROLLBACK;')
        current_app.logger.error(f"An unexpected error occurred during attachment deletion: {e}")
        return jsonify({"error": "An unexpected server error occurred during attachment deletion", "details": str(e)}), 500
    finally:
        if conn: conn.close()


@logs_bp.route('/<int:log_record_id>/attachments', methods=['GET'])
@login_required
def get_log_record_attachments(log_record_id):
    conn = None
    try:
        conn = get_db_connection()
        attachments = conn.execute("SELECT * FROM attachments WHERE log_record_id = ?", (log_record_id,)).fetchall()

        attachments_list = [dict(att) for att in attachments]
        return jsonify(attachments_list), 200
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred fetching attachments: {e}")
        return jsonify({"error": "An unexpected server error occurred fetching attachments", "details": str(e)}), 500
    finally:
        if conn: conn.close()

@logs_bp.route('/config/allowed_extensions', methods=['GET'])
@login_required
def get_allowed_extensions():
    # Access ALLOWED_EXTENSIONS from Config object
    return jsonify(list(Config.ALLOWED_EXTENSIONS)), 200