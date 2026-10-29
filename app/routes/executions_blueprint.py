from flask import Blueprint, jsonify, current_app
from sqlalchemy.orm import joinedload

from app.models.cell import Cell
from app.models.notebook import Notebook

from app.executor.executor_service import CellExecutionService
from app.database.db import db

import traceback
import logging
import time


logger = logging.getLogger(__name__)


executions_bp = Blueprint(
    "executions",
    __name__,
    url_prefix="/api/executions"
)


# ==========================================================
# HELPERS
# ==========================================================

def success_response(data=None, message=None, status=200):

    response = {
        "success": True
    }

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    return jsonify(response), status


def error_response(message, status=400, details=None):

    response = {
        "success": False,
        "error": message
    }

    if details:
        response["details"] = details

    return jsonify(response), status


from app.utils.current_user import get_current_user_id


def get_user_cell(cell_id: int, user_id: int):

    return (
        Cell.query
        .options(joinedload(Cell.notebook))
        .join(Notebook, Notebook.id == Cell.notebook_id)
        .filter(
            Cell.id == cell_id,
            Notebook.user_id == user_id
        )
        .first()
    )


# ==========================================================
# EXECUTE CELL
# ==========================================================

@executions_bp.route("/cells/<int:cell_id>/execute", methods=["POST"])
def execute_cell(cell_id):

    start_time = time.time()

    try:

        user_id = get_current_user_id()

        # ==================================================
        # VALIDAR ACESSO + BUSCAR CÉLULA
        # ==================================================

        cell = get_user_cell(cell_id, user_id)

        if not cell:
            return error_response(
                "Célula não encontrada ou sem permissão",
                404
            )

        # ==================================================
        # EXECUÇÃO
        # ==================================================

        if cell.cell_type == "python" and not current_app.config.get("ENABLE_KERNELS", True):
            return error_response(
                "Execução Python está temporariamente desabilitada neste ambiente. "
                "Ela será reativada após a implantação de um sandbox isolado.",
                503
            )

        logger.info(
            f"[EXECUTION] user={user_id} "
            f"cell={cell.id} "
            f"type={cell.cell_type}"
        )

        result = CellExecutionService.execute_cell(cell)

        execution_time = round(time.time() - start_time, 4)

        # ==================================================
        # NORMALIZAÇÃO DE RESPOSTA
        # ==================================================

        if not isinstance(result, dict):

            logger.error(
                f"Executor retornou tipo inválido: {type(result)}"
            )

            return error_response(
                "Executor retornou resposta inválida",
                500
            )

        result["execution_time"] = execution_time
        result["cell_id"] = cell.id

        status = 200 if result.get("success") else 400

        logger.info(
            f"[EXECUTION_FINISHED] "
            f"cell={cell.id} "
            f"success={result.get('success')} "
            f"time={execution_time}s"
        )

        return jsonify(result), status

    except Exception as e:

        logger.exception(
            f"[EXECUTION_ERROR] cell_id={cell_id}"
        )

        return error_response(
            "Erro interno durante execução da célula",
            500,
            details=str(e)
        )