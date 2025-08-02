# trustlog_backend/allowed_file.py

from trustlog_backend.config import Config # Absolute import of Config class

# Helper function for file extension validation
def allowed_file(filename):
    """Checks if the file extension is allowed based on ALLOWED_EXTENSIONS from Config."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS