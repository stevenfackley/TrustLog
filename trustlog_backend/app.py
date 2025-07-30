# app.py
from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime
import json
from flask_cors import CORS # Import CORS

app = Flask(__name__)
DATABASE = 'tracking_log.db'
UPLOAD_FOLDER = 'uploads' # Directory to store attachments

# Configure Flask to accept JSON for POST requests
app.config['JSON_AS_ASCII'] = False # Allows non-ASCII characters in JSON responses

# Create the upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}") # For debugging

# Enable CORS for all routes (for development with Svelte frontend)
CORS(app)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # This allows accessing columns by name (e.g., row['column_name'])
    # [cite_start]Enable WAL mode for better performance on SQLite [cite: 11]
    conn.execute('PRAGMA journal_mode=WAL;')
    # [cite_start]Set synchronous mode to NORMAL for improved commit performance [cite: 11]
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn

def init_db():
    """Initializes the database by creating tables if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # [cite_start]Create log_records table based on the schema document [cite: 257]
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_of_incident TEXT NOT NULL,
                time_of_incident TEXT,
                category TEXT NOT NULL,
                description_of_incident TEXT NOT NULL,
                [cite_start]impact_types TEXT NOT NULL, -- Storing as JSON array for multi-select [cite: 259]
                impact_details TEXT,
                supporting_evidence_snippet TEXT,
                exhibit_reference TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # [cite_start]Create attachments table based on the schema document [cite: 267]
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
        # [cite_start]Create indexes for performance on frequently queried columns [cite: 272]
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_date ON log_records (date_of_incident);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_category ON log_records (category);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attachment_log_id ON attachments (log_record_id);')
        conn.commit()
    print("Database initialized or already exists.") # For debugging/confirmation

# Initialize the database when the application starts within the Flask application context
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

    # [cite_start]Server-side input validation [cite: 172]
    required_fields = ['date_of_incident', 'category', 'description_of_incident', 'impact_types']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing or empty required field: {field}"}), 400

    # [cite_start]Ensure impact_types is a list and convert to JSON string for storage [cite: 260]
    impact_types = data.get('impact_types')
    if not isinstance(impact_types, list):
        return jsonify({"error": "impact_types must be a list"}), 400
    impact_types_json = json.dumps(impact_types)

    date_of_incident = data.get('date_of_incident')
    time_of_incident = data.get('time_of_incident', None) # Optional
    category = data.get('category')
    description_of_incident = data.get('description_of_incident')
    impact_details = data.get('impact_details', None) # Optional
    # Only include supporting_evidence_snippet if provided and relevant
    supporting_evidence_snippet = data.get('supporting_evidence_snippet', None)
    exhibit_reference = data.get('exhibit_reference', None) # Optional

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # [cite_start]Use parameterized queries to prevent SQL injection [cite: 293]
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
        conn.commit() # Commit the transaction to save changes to the database
        log_id = cursor.lastrowid # Get the ID of the newly inserted row
        conn.close()
        return jsonify({"message": "Log record created successfully", "id": log_id}), 201 # 201 Created status
    except sqlite3.Error as e:
        print(f"Database error during log record creation: {e}")
        return jsonify({"error": "Could not create log record", "details": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred during log record creation: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

# You can add more API routes here as needed (e.g., for fetching records, attachments)

if __name__ == '__main__':
    # For local development, running with debug=True and host='0.0.0.0' is convenient.
    # debug=True: Enables auto-reloading and debugger. **MUST be False in production.**
    # host='0.0.0.0': Makes the server accessible from other devices on your local network.
    # When deploying to Raspberry Pi with Gunicorn/Nginx, debug should be False
    # and host should be 127.0.0.1 (or specific internal IP) as Nginx will proxy requests.
    app.run(debug=True, host='0.0.0.0')