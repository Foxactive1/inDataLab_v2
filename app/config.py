"""
InDataLab - Configurações Globais
Compatível com:
- Localhost
- Pydroid
- PythonAnywhere
- Railway
- Docker
"""

import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


class Config:
    """Configuração base"""

    # =========================================================
    # Ambiente
    # =========================================================
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'sua-chave-jwt-muito-segura')
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    IS_PRODUCTION = FLASK_ENV == "production"

    IS_PYTHONANYWHERE = bool(os.getenv("PYTHONANYWHERE_SITE"))

    IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))

    # =========================================================
    # Segurança
    # =========================================================

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "indatalab-dev-secret-change-in-production"
    )

    # =========================================================
    # Diretórios
    # =========================================================

    INSTANCE_PATH = os.path.abspath(
        os.path.join(PROJECT_ROOT, "instance")
    )
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "uploads")

    os.makedirs(INSTANCE_PATH, exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # =========================================================
    # Banco de Dados
    # =========================================================

    SQLITE_PATH = os.path.join(INSTANCE_PATH, "indatalab.db")

    DEFAULT_SQLITE_URI = f"sqlite:///{SQLITE_PATH}"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        DEFAULT_SQLITE_URI
    )

    # Railway usa postgres://
    # SQLAlchemy moderno prefere postgresql://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = (
            SQLALCHEMY_DATABASE_URI.replace(
                "postgres://",
                "postgresql://",
                1
            )
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuração do engine: connect_args específico para SQLite
    engine_options = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    SQLALCHEMY_ENGINE_OPTIONS = engine_options

    # =========================================================
    # Uploads
    # =========================================================

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

    ALLOWED_EXTENSIONS = {
        "csv",
        "txt",
        "json",
        "xlsx",   # corrigido: vírgula, não ponto
        "db"
    }

    # =========================================================
    # Groq API
    # =========================================================

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    GROQ_MODEL = os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile"
    )

    GROQ_TIMEOUT = int(
        os.getenv("GROQ_TIMEOUT", 30)
    )

    GROQ_MAX_TOKENS = int(
        os.getenv("GROQ_MAX_TOKENS", 2048)
    )

    GROQ_TEMPERATURE = float(
        os.getenv("GROQ_TEMPERATURE", 0.7)
    )

    # =========================================================
    # Sessão
    # =========================================================

    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SECURE = IS_PRODUCTION

    # =========================================================
    # Logging
    # =========================================================

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # =========================================================
    # Executor / Kernels
    # =========================================================

    ENABLE_KERNELS = (
        os.getenv("ENABLE_KERNELS", "true").lower() == "true"
    )

    # =========================================================
    # Performance
    # =========================================================

    JSON_SORT_KEYS = False


# =============================================================
# Development
# =============================================================

class DevelopmentConfig(Config):

    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


# =============================================================
# Production
# =============================================================

class ProductionConfig(Config):

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


# =============================================================
# Testing
# =============================================================

class TestingConfig(Config):

    TESTING = True

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    WTF_CSRF_ENABLED = False


# =============================================================
# Config Selector
# =============================================================

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}

CURRENT_CONFIG = config_by_name.get(
    os.getenv("FLASK_ENV", "development"),
    DevelopmentConfig
)