"""
Blueprint: Notebooks

CRUD de notebooks do InDataLab
"""

from flask import Blueprint, request, jsonify
import logging
import traceback

from app.services.notebook_service import NotebookService

from app.utils import (
    APIResponse,
    ValidateRequest,
    serialize_model
)


logger = logging.getLogger(__name__)


notebooks_bp = Blueprint(
    'notebooks',
    __name__,
    url_prefix='/api/notebooks'
)


# ==========================================================
# HELPERS
# ==========================================================

def get_current_user_id():
    """
    MVP authentication.

    Futuro:
    - JWT
    - OAuth
    - Session auth
    """

    return 1


def parse_pagination():

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    page = max(page, 1)

    # proteção contra abuso
    per_page = min(max(per_page, 1), 100)

    return page, per_page


def parse_boolean_arg(name):

    value = request.args.get(name)

    if value is None:
        return None

    return value.lower() == 'true'


def handle_exception(e):

    logger.exception(str(e))

    return jsonify(
        APIResponse.internal_error(
            "Erro interno no servidor"
        )[0]
    ), 500


# ==========================================================
# CREATE NOTEBOOK
# ==========================================================

@notebooks_bp.route('', methods=['POST'])
def create_notebook():

    try:

        user_id = get_current_user_id()

        data = request.get_json(silent=True) or {}

        # ==================================================
        # VALIDATIONS
        # ==================================================

        validation = ValidateRequest.required_fields(
            data,
            ['title']
        )

        if validation:
            return jsonify(validation[0]), validation[1]

        validation = ValidateRequest.field_length(
            data,
            'title',
            min_length=1,
            max_length=255
        )

        if validation:
            return jsonify(validation[0]), validation[1]

        # ==================================================
        # CREATE
        # ==================================================

        notebook, error = NotebookService.create_notebook(
            user_id=user_id,
            title=data.get('title'),
            description=data.get('description'),
            is_public=data.get('is_public', False),
            kernel_type=data.get('kernel_type', 'python3')
        )

        if error:
            resp, code = APIResponse.bad_request(error)
            return jsonify(resp), code

        logger.info(
            f'[NOTEBOOK_CREATED] '
            f'user={user_id} '
            f'notebook={notebook.id}'
        )

        resp, code = APIResponse.success(
            data=serialize_model(notebook),
            message='Notebook criado com sucesso',
            status_code=201
        )

        return jsonify(resp), code

    except Exception as e:
        return handle_exception(e)


# ==========================================================
# LIST NOTEBOOKS
# ==========================================================

@notebooks_bp.route('', methods=['GET'])
def list_notebooks():

    try:

        user_id = get_current_user_id()

        page, per_page = parse_pagination()

        is_archived = parse_boolean_arg(
            'is_archived'
        )

        notebooks, total, pages = (
            NotebookService.list_notebooks(
                user_id=user_id,
                is_archived=is_archived,
                page=page,
                per_page=per_page
            )
        )

        resp, code = APIResponse.success(
            data={
                'notebooks': notebooks,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                }
            }
        )

        return jsonify(resp), code

    except Exception as e:
        return handle_exception(e)


# ==========================================================
# GET NOTEBOOK
# ==========================================================

@notebooks_bp.route('/<int:notebook_id>', methods=['GET'])
def get_notebook(notebook_id):

    try:

        user_id = get_current_user_id()

        notebook = NotebookService.get_notebook(
            notebook_id,
            user_id
        )

        if not notebook:

            resp, code = APIResponse.not_found(
                'Notebook'
            )

            return jsonify(resp), code

        stats = NotebookService.get_notebook_stats(
            notebook_id,
            user_id
        )

        resp, code = APIResponse.success(
            data={
                'notebook': serialize_model(notebook),
                'stats': stats
            }
        )

        return jsonify(resp), code

    except Exception as e:
        return handle_exception(e)


# ==========================================================
# UPDATE NOTEBOOK
# ==========================================================

@notebooks_bp.route('/<int:notebook_id>', methods=['PUT'])
def update_notebook(notebook_id):

    try:

        user_id = get_current_user_id()

        data = request.get_json(silent=True) or {}

        if not data:

            resp, code = APIResponse.bad_request(
                'Nenhum dado enviado'
            )

            return jsonify(resp), code

        # ==================================================
        # MASS ASSIGNMENT PROTECTION
        # ==================================================

        allowed_fields = {
            'title',
            'description',
            'is_public',
            'is_archived',
            'kernel_type'
        }

        filtered_data = {
            key: value
            for key, value in data.items()
            if key in allowed_fields
        }

        if not filtered_data:

            resp, code = APIResponse.bad_request(
                'Nenhum campo válido enviado'
            )

            return jsonify(resp), code

        # ==================================================
        # UPDATE
        # ==================================================

        notebook, error = NotebookService.update_notebook(
            notebook_id=notebook_id,
            user_id=user_id,
            **filtered_data
        )

        if error:

            resp, code = APIResponse.bad_request(
                error
            )

            return jsonify(resp), code

        logger.info(
            f'[NOTEBOOK_UPDATED] '
            f'user={user_id} '
            f'notebook={notebook.id}'
        )

        resp, code = APIResponse.success(
            data=serialize_model(notebook),
            message='Notebook atualizado'
        )

        return jsonify(resp), code

    except Exception as e:
        return handle_exception(e)


# ==========================================================
# DELETE NOTEBOOK
# ==========================================================

@notebooks_bp.route('/<int:notebook_id>', methods=['DELETE'])
def delete_notebook(notebook_id):

    try:

        user_id = get_current_user_id()

        success, error = NotebookService.delete_notebook(
            notebook_id,
            user_id
        )

        if not success:

            resp, code = APIResponse.bad_request(
                error
            )

            return jsonify(resp), code

        logger.info(
            f'[NOTEBOOK_DELETED] '
            f'user={user_id} '
            f'notebook={notebook_id}'
        )

        resp, code = APIResponse.success(
            message='Notebook deletado'
        )

        return jsonify(resp), code

    except Exception as e:
        return handle_exception(e)