# trustlog_backend/app.py

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from trustlog_backend.config import Config
from trustlog_backend.database import init_db
from trustlog_backend.models import User
from trustlog_backend.auth import auth_bp
from trustlog_backend.routes.logs import logs_bp # Import logs blueprint

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, supports_credentials=True)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import jsonify, request
        if request.path.startswith('/api/'):
            return jsonify({"error": "Unauthorized: Please log in to access this resource"}), 401
        return "Unauthorized access. Please log in.", 401 # Fallback for non-API, non-redirect

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(logs_bp, url_prefix='/api/log_records')

    # Initialize the database within the app context
    with app.app_context():
        init_db()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0')