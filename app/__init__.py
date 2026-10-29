"""
InDataLab - Aplicação Principal (ETAPA 2/3)
Factory Flask - arquitetura consolidada
"""

import os
from flask import Flask, jsonify, render_template, send_from_directory, request, redirect, url_for
from flask_jwt_extended import verify_jwt_in_request

from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt

from .config import Config, CURRENT_CONFIG
from .database.db import db, migrate
from app.routes.system_routes import system_bp


load_dotenv(".env")


def create_app(config_class=CURRENT_CONFIG):
    """
    Factory da aplicação Flask
    """

    # =========================================================
    # 1. Criar app base
    # =========================================================
    app = Flask(__name__)

    # =========================================================
    # 2. Carregar configuração ativa
    # =========================================================
    app.config.from_object(config_class)

    # =========================================================
    # 3. Configurar instance_path corretamente
    # =========================================================
    app.instance_path = os.path.abspath(config_class.INSTANCE_PATH)
    app.instance_relative_config = False

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # =========================================================
    # 4. Inicializar extensões
    # =========================================================
    db.init_app(app)
    migrate.init_app(app, db)

    # Inicializar extensões de segurança e CORS para frontend hospedado no Vercel.
    JWTManager(app)
    Bcrypt(app)

    allowed_origins = [
        origin.strip().rstrip("/")
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    CORS(
        app,
        resources={r"/*": {"origins": allowed_origins}},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        supports_credentials=False,
        max_age=600,
    )

    # Registrar todos os modelos sem modificar o esquema Neon existente.
    from . import models  # noqa: F401

    # =========================================================
    # 6. Registrar Blueprints
    # =========================================================
    from .routes import (
        notebooks_bp,
        cells_bp,
        executions_bp,
        copilot_bp,
        datasets_bp
    )
    from .routes.auth_blueprint import auth_bp  # <-- NOVO

    app.register_blueprint(notebooks_bp)
    app.register_blueprint(cells_bp)
    app.register_blueprint(executions_bp)
    app.register_blueprint(copilot_bp)
    app.register_blueprint(datasets_bp)
    app.register_blueprint(auth_bp)   # <-- NOVO
    app.register_blueprint(system_bp)

    # Rejeitar acesso anônimo antes dos handlers (incluindo Copilot e datasets).
    @app.before_request
    def require_api_auth():
        # Preflight CORS não carrega JWT; deve chegar ao handler OPTIONS.
        if request.method == "OPTIONS":
            return None
        if request.path.startswith("/api/"):
            verify_jwt_in_request()

    # =========================================================
    # 7. Servir arquivos estáticos de gráficos (plotly/matplotlib)
    # =========================================================
    @app.route('/uploads/plots/<path:filename>')
    def serve_plot(filename):
        """Serve arquivos de gráficos gerados (PNG/HTML)."""
        plots_dir = os.path.join(app.root_path, 'uploads', 'plots')
        return send_from_directory(plots_dir, filename)

    # =========================================================
    # 8. Health Check
    # =========================================================
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "InDataLab",
            "environment": app.config.get("FLASK_ENV", "development")
        }), 200

    # =========================================================
    # 9. Frontend
    # =========================================================
    
    @app.route("/login")
    def login_page():
        return render_template("login_bootstrap.html")

    @app.route("/")
    def index():
        return render_template("index.html")

	
	 
    # =========================================================
    # 10. Error Handlers
    # =========================================================
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": "Rota não encontrada",
            "status": 404
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "status": 500
        }), 500

    return app