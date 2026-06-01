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
logger = logging.getLogger(__name__)
import os

bp = Blueprint(
    'datasets',
    __name__,
    url_prefix='/api/notebooks/<int:notebook_id>/datasets'
)

# ==========================================================
# HELPERS
# ==========================================================

def success_response(data=None, message=None, status=200, extra=None):
    response = {'success': True}

    if message:
        response['message'] = message

    if data is not None:
        response['data'] = data
        
    if extra and isinstance(extra, dict):
        response.update(extra)

    return jsonify(response), status


def error_response(message, status=400):
    return jsonify({
        'success': False,
        'error': message
    }), status


def get_user_id():
    """MVP authentication."""
    user = User.query.filter_by(is_active=True).first()

    if not user:
        user = User(
            name='Default',
            email='default@example.com',
            password_hash='',
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


# ==========================================================
# UPLOAD DATASET (ATUALIZADO)
# ==========================================================

@bp.route('', methods=['POST'])
def upload_dataset(notebook_id):
    if notebook_id is None or notebook_id <= 0:
        return error_response('ID do notebook inválido', 400)

    user_id = get_user_id()

    if not validate_notebook_owner(notebook_id, user_id):
        return error_response('Notebook não encontrado ou sem permissão', 404)

    if 'file' not in request.files:
        return error_response('Nenhum arquivo enviado')

    file = request.files['file']
    if file.filename == '':
        return error_response('Arquivo vazio')

    try:
        # Salva o dataset (a lógica interna do service já injeta a conexão padrão se for .db)
        dataset = save_dataset(file=file, notebook_id=notebook_id, user_id=user_id)
        refresh_datasets_in_session(notebook_id)
        logger.info(f'Dataset enviado: {dataset.filename} (notebook {notebook_id})')
        
        # Resgata o notebook para verificar se ele ganhou uma conexão padrão automática
        notebook = Notebook.query.get(notebook_id)
        extra_info = {
            "default_sql_connection": notebook.default_sql_connection if notebook else None
        }

        return success_response(
            data=dataset.to_dict(), 
            message='Dataset enviado com sucesso',
            extra=extra_info
        )
    except Exception as e:
        logger.exception(f'Erro ao fazer upload para notebook {notebook_id}')
        return error_response(str(e), 500)

# ==========================================================
# LIST DATASETS
# ==========================================================

@bp.route('', methods=['GET'])
def list_datasets(notebook_id):
    user_id = get_user_id()

    if not validate_notebook_owner(notebook_id, user_id):
        return error_response('Notebook não encontrado ou sem permissão', 404)

    datasets = Dataset.query.filter_by(notebook_id=notebook_id).all()
    return success_response(data=[d.to_dict() for d in datasets])


# ==========================================================
# GET DATASET DATA
# ==========================================================

@bp.route('/<int:dataset_id>/data', methods=['GET'])
def get_dataset_data(notebook_id, dataset_id):
    user_id = get_user_id()

    if not validate_notebook_owner(notebook_id, user_id):
        return error_response('Notebook não encontrado ou sem permissão', 404)

    dataset = get_dataset(notebook_id, dataset_id)
    if not dataset:
        return error_response('Dataset não encontrado', 404)

    try:
        data = load_dataset_data(
            dataset_id=dataset_id,
            user_id=user_id,
            notebook_id=notebook_id
        )
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), 500)


# ==========================================================
# SET DEFAULT SQL CONNECTION
# ==========================================================

@bp.route('/<int:dataset_id>/set_as_sql_connection', methods=['POST'])
def set_dataset_as_sql_connection(notebook_id, dataset_id):
    user_id = get_user_id()

    if not validate_notebook_owner(notebook_id, user_id):
        return error_response('Notebook não encontrado ou sem permissão', 404)

    dataset = get_dataset(notebook_id, dataset_id)
    if not dataset:
        return error_response('Dataset não encontrado', 404)

    is_sqlite = (dataset.file_type == 'db') or getattr(dataset, 'is_sql_database', False)
    if not is_sqlite:
        return error_response('Este dataset não é um banco SQLite (.db)', 400)

    notebook = Notebook.query.get(notebook_id)
    notebook.default_sql_connection = dataset.file_path
    db.session.commit()

    refresh_datasets_in_session(notebook_id)

    logger.info(f'Notebook {notebook_id}: default_sql_connection definido para {dataset.file_path}')
    return success_response(message=f'Conexão SQL definida para {dataset.filename}')

# ==========================================================
# INSPECT SQLITE DATABASE
# ==========================================================

@bp.route('/<int:dataset_id>/inspect_sql', methods=['GET'])
def inspect_dataset_sql(notebook_id, dataset_id):
    user_id = get_user_id()

    if not validate_notebook_owner(notebook_id, user_id):
        return error_response('Notebook não encontrado ou sem permissão', 404)

    dataset = get_dataset(notebook_id, dataset_id)
    if not dataset:
        return error_response('Dataset não encontrado', 404)

    is_sqlite = (dataset.file_type == 'db' or getattr(dataset, 'is_sql_database', False))
    if not is_sqlite:
        return error_response('Dataset não é um banco SQLite')

    try:
        info = DatabaseInspector.inspect_database(dataset.file_path)
        return success_response(data=info)
    except Exception as e:
        return error_response(str(e), 500)


# ==========================================================
# DELETE DATASET
# ==========================================================

@bp.route('/<int:dataset_id>', methods=['DELETE'])
def delete_dataset(notebook_id, dataset_id):
    user_id = get_user_id()

    if not validate_notebook_owner(notebook_id, user_id):
        return error_response('Notebook não encontrado ou sem permissão', 404)

    dataset = get_dataset(notebook_id, dataset_id)
    if not dataset:
        return error_response('Dataset não encontrado', 404)

    try:
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)

        db.session.delete(dataset)
        db.session.commit()

        refresh_datasets_in_session(notebook_id)
        return success_response(message='Dataset removido com sucesso')
    except Exception as e:
        return error_response(str(e), 500)
