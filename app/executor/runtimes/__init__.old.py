"""
InDataLab - Aplicação Principal (ETAPA 2/3)
Factory Flask - arquitetura consolidada
"""

import os
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

from .config import Config, CURRENT_CONFIG  # <-- EXPORTADO
from .database.db import db, migrate

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

    # =========================================================
    # 5. Garantir criação de tabelas (DEV/MVP)
    # =========================================================
    with app.app_context():
        # Importar todos os modelos de uma vez (evita importações parciais)
        from .models import (
            User, Notebook, Cell, Execution,
            Dataset, AIConversation
        )
        db.create_all()

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

    app.register_blueprint(notebooks_bp)
    app.register_blueprint(cells_bp)
    app.register_blueprint(executions_bp)
    app.register_blueprint(copilot_bp)
    app.register_blueprint(datasets_bp)

    # =========================================================
    # 7. Health Check
    # =========================================================
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "InDataLab",
            "environment": app.config.get("FLASK_ENV", "development")
        }), 200

    # =========================================================
    # 8. Frontend
    # =========================================================
    @app.route("/")
    def index():
        return render_template("index.html")

    # =========================================================
    # 9. Error Handlers
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