from flask import Blueprint, request, jsonify
from app.executor.kernel_manager import refresh_datasets_in_session
from app.services.dataset_service import (
    save_dataset,
    load_dataset_data
)

from app.models.dataset import Dataset
from app.models.notebook import Notebook
from app.models.user import User

from app.database.db import db
from app.sql.inspector import DatabaseInspector

import logging
import os

logger = logging.getLogger(__name__)

bp = Blueprint(
    "datasets",
    __name__,
    url_prefix="/api/notebooks/<int:notebook_id>/datasets"
)

# ==========================================================
# HELPERS
# ==========================================================

def success_response(data=None, message=None, status=200, extra=None):

    response = {
        "success": True
    }

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    if extra and isinstance(extra, dict):
        response.update(extra)

    return jsonify(response), status


# Adicione esta função helper no início do arquivo, após os imports

def resolve_sqlite_path(relative_path: str) -> str:
    """Converte caminho relativo de SQLite para absoluto usando UPLOAD_FOLDER"""
    from flask import current_app
    if not relative_path:
        return None
    # Se já for absoluto, retorna como está (fallback)
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)
def error_response(message, status=400):

    return jsonify({
        "success": False,
        "error": message
    }), status


def get_user_id():
    """
    MVP Authentication.
    """

    user = User.query.filter_by(
        is_active=True
    ).first()

    if not user:

        user = User(
            name="Default",
            email="default@example.com",
            password_hash="",
            is_active=True
        )

        db.session.add(user)
        db.session.commit()

    return user.id


def validate_notebook_owner(notebook_id, user_id):

    notebook = Notebook.query.filter_by(
        id=notebook_id,
        user_id=user_id
    ).first()

    return notebook is not None


def get_dataset(notebook_id, dataset_id):

    return Dataset.query.filter_by(
        id=dataset_id,
        notebook_id=notebook_id
    ).first()


def validate_access(notebook_id):

    user_id = get_user_id()

    if not validate_notebook_owner(
        notebook_id,
        user_id
    ):
        return None, error_response(
            "Notebook não encontrado ou sem permissão",
            404
        )

    return user_id, None


# ==========================================================
# UPLOAD DATASET
# ==========================================================

@bp.route("", methods=["POST"])
def upload_dataset(notebook_id):

    user_id, error = validate_access(
        notebook_id
    )

    if error:
        return error

    if "file" not in request.files:
        return error_response(
            "Nenhum arquivo enviado"
        )

    file = request.files["file"]

    if file.filename == "":
        return error_response(
            "Arquivo vazio"
        )

    try:

        dataset = save_dataset(
            file=file,
            notebook_id=notebook_id,
            user_id=user_id
        )

        # Pré-processa SQLite
        if dataset.is_sql_database:

            try:

                metadata = (
                    DatabaseInspector.inspect_database(
                        dataset.file_path
                    )
                )

                dataset.extra_metadata = metadata

                db.session.commit()

            except Exception as sql_error:

                logger.exception(
                    f"Erro ao inspecionar SQLite: "
                    f"{sql_error}"
                )

        refresh_datasets_in_session(
            notebook_id
        )

        notebook = Notebook.query.get(
            notebook_id
        )

        logger.info(
            f"Dataset enviado: "
            f"{dataset.filename}"
        )

        return success_response(
            data=dataset.to_dict(),
            message="Dataset enviado com sucesso",
            extra={
                "default_sql_connection":
                    notebook.default_sql_connection
                    if notebook
                    else None
            }
        )

    except Exception as e:

        logger.exception(
            "Erro no upload"
        )

        return error_response(
            str(e),
            500
        )


# ==========================================================
# LIST DATASETS
# ==========================================================

@bp.route("", methods=["GET"])
def list_datasets(notebook_id):

    _, error = validate_access(
        notebook_id
    )

    if error:
        return error

    datasets = Dataset.query.filter_by(
        notebook_id=notebook_id
    ).all()

    return success_response(
        data=[d.to_dict() for d in datasets]
    )


# ==========================================================
# GET DATASET DATA
# ==========================================================

@bp.route("/<int:dataset_id>/data", methods=["GET"])
def get_dataset_data(
    notebook_id,
    dataset_id
):

    user_id, error = validate_access(
        notebook_id
    )

    if error:
        return error

    dataset = get_dataset(
        notebook_id,
        dataset_id
    )

    if not dataset:
        return error_response(
            "Dataset não encontrado",
            404
        )

    try:

        data = load_dataset_data(
            dataset_id=dataset_id,
            user_id=user_id,
            notebook_id=notebook_id
        )

        return success_response(
            data=data
        )

    except Exception as e:

        return error_response(
            str(e),
            500
        )


# ==========================================================
# SET DEFAULT SQL CONNECTION
# ==========================================================

@bp.route(
    "/<int:dataset_id>/set_as_sql_connection",
    methods=["POST"]
)
def set_dataset_as_sql_connection(
    notebook_id,
    dataset_id
):

    _, error = validate_access(
        notebook_id
    )

    if error:
        return error

    dataset = get_dataset(
        notebook_id,
        dataset_id
    )

    if not dataset:
        return error_response(
            "Dataset não encontrado",
            404
        )

    is_sqlite = (
        dataset.file_type == "db"
        or dataset.is_sql_database
    )

    if not is_sqlite:

        return error_response(
            "Este dataset não é SQLite",
            400
        )

    notebook = Notebook.query.get(
        notebook_id
    )

    notebook.default_sql_connection = (
        dataset.file_path
    )

    db.session.commit()

    refresh_datasets_in_session(
        notebook_id
    )

    return success_response(
        message=(
            f"Conexão SQL definida para "
            f"{dataset.filename}"
        )
    )


# ==========================================================
# INSPECT SQLITE DATABASE
# ==========================================================

@bp.route(
    "/<int:dataset_id>/inspect_sql",
    methods=["GET"]
)
def inspect_dataset_sql(
    notebook_id,
    dataset_id
):

    _, error = validate_access(
        notebook_id
    )

    if error:
        return error

    dataset = get_dataset(
        notebook_id,
        dataset_id
    )

    if not dataset:
        return error_response(
            "Dataset não encontrado",
            404
        )

    is_sqlite = (
        dataset.file_type == "db"
        or dataset.is_sql_database
    )

    if not is_sqlite:
        return error_response(
            "Dataset não é SQLite",
            400
        )

    if not dataset.file_path:
        return error_response(
            "file_path não definido",
            400
        )

    if not os.path.exists(
        dataset.file_path
    ):
        return error_response(
            f"Arquivo não encontrado: "
            f"{dataset.file_path}",
            404
        )

    try:

        result = (
            DatabaseInspector.inspect_database(
                dataset.file_path
            )
        )

        return success_response(
            data=result,
            message=(
                "Banco inspecionado "
                "com sucesso"
            )
        )

    except Exception as e:

        logger.exception(
            "Erro na inspeção SQL"
        )

        return error_response(
            str(e),
            500
        )


# ==========================================================
# GET SQL SCHEMA
# ==========================================================

@bp.route(
    "/<int:dataset_id>/schema",
    methods=["GET"]
)
def get_dataset_schema(
    notebook_id,
    dataset_id
):

    _, error = validate_access(
        notebook_id
    )

    if error:
        return error

    dataset = get_dataset(
        notebook_id,
        dataset_id
    )

    if not dataset:
        return error_response(
            "Dataset não encontrado",
            404
        )

    if not dataset.extra_metadata:
        return error_response(
            "Schema ainda não gerado",
            404
        )

    return success_response(
        data=dataset.extra_metadata
    )


# ==========================================================
# DELETE DATASET
# ==========================================================

@bp.route(
    "/<int:dataset_id>",
    methods=["DELETE"]
)
def delete_dataset(
    notebook_id,
    dataset_id
):

    _, error = validate_access(
        notebook_id
    )

    if error:
        return error

    dataset = get_dataset(
        notebook_id,
        dataset_id
    )

    if not dataset:
        return error_response(
            "Dataset não encontrado",
            404
        )

    try:

        if (
            dataset.file_path
            and os.path.exists(
                dataset.file_path
            )
        ):
            os.remove(
                dataset.file_path
            )

        db.session.delete(
            dataset
        )

        db.session.commit()

        refresh_datasets_in_session(
            notebook_id
        )

        return success_response(
            message=(
                "Dataset removido "
                "com sucesso"
            )
        )

    except Exception as e:

        logger.exception(
            "Erro ao remover dataset"
        )

        return error_response(
            str(e),
            500
        )