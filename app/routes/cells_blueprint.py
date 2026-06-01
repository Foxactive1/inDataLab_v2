"""
Blueprint: Cells
Rotas CRUD para células dentro de notebooks (suporte a python, sql, markdown, ai)
"""

from flask import Blueprint, request, jsonify

from app.services.cell_service import CellService
from app.utils import APIResponse, ValidateRequest, serialize_model, serialize_models


cells_bp = Blueprint(
    'cells',
    __name__,
    url_prefix='/api/notebooks/<int:notebook_id>/cells'
)


def _get_user_id():
    # Hardcoded para MVP - substituir por autenticação real
    return 1


# CRIAR CÉLULA
@cells_bp.route('', methods=['POST'])
def create_cell(notebook_id):
    """
    POST /api/notebooks/{notebook_id}/cells
    Body: {
        "cell_type": "python" | "sql" | "markdown" | "ai",
        "content": "...",
        "position": 0 (opcional),
        "tags": "tag1,tag2" (opcional),
        "sql_connection": "/path/to/db.db" (opcional, apenas para sql)
    }
    """
    try:
        user_id = _get_user_id()
        data = request.get_json() or {}
        
        # Validação de campos obrigatórios
        validation = ValidateRequest.required_fields(data, ['cell_type', 'content'])
        if validation:
            return jsonify(validation[0]), validation[1]
        
        cell_type = data.get('cell_type')
        # Compatibilidade com frontend antigo
        if cell_type == 'code':
            cell_type = 'python'
        
        content = data.get('content')
        position = data.get('position')
        tags = data.get('tags')
        sql_connection = data.get('sql_connection')  # usado apenas para SQL
        
        cell, error = CellService.create_cell(
            notebook_id=notebook_id,
            user_id=user_id,
            cell_type=cell_type,
            content=content,
            position=position,
            tags=tags,
            sql_connection=sql_connection
        )
        
        if error:
            resp, code = APIResponse.bad_request(error)
            return jsonify(resp), code
        
        resp, code = APIResponse.success(
            data=serialize_model(cell),
            message="Célula criada",
            status_code=201
        )
        return jsonify(resp), code
    
    except Exception as e:
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code

@cells_bp.route('/<int:cell_id>/move', methods=['POST'])
def move_cell(notebook_id, cell_id):
    direction = request.args.get('direction')
    if direction not in ('up', 'down'):
        return jsonify(APIResponse.bad_request("direction deve ser 'up' ou 'down'")[0]), 400
    
    user_id = _get_user_id()
    success, error = CellService.move_cell(cell_id, user_id, direction)
    if not success:
        return jsonify(APIResponse.bad_request(error)[0]), 400
    return jsonify(APIResponse.success(message="Célula movida")[0]), 200
# LISTAR CÉLULAS
@cells_bp.route('', methods=['GET'])
def list_cells(notebook_id):
    """
    GET /api/notebooks/{notebook_id}/cells?cell_type=python
    """
    try:
        user_id = _get_user_id()
        cell_type = request.args.get('cell_type')
        
        # Verificar se o notebook existe e pertence ao usuário (evita erro 400 genérico)
        from app.services.notebook_service import NotebookService
        notebook = NotebookService.get_notebook(notebook_id, user_id)
        if not notebook:
            resp, code = APIResponse.not_found("Notebook")
            return jsonify(resp), code
        
        cells, error = CellService.list_cells(
            notebook_id=notebook_id,
            user_id=user_id,
            cell_type=cell_type
        )
        
        if error:
            # Log do erro para depuração
            print(f"[ERROR] CellService.list_cells: {error}")
            # Retorna 404 se o erro indicar que não há células ou notebook não existe
            if "not found" in error.lower() or "permissão" in error.lower():
                resp, code = APIResponse.not_found("Células")
            else:
                resp, code = APIResponse.bad_request(error)
            return jsonify(resp), code
        
        resp, code = APIResponse.success(
            data={'cells': serialize_models(cells)}
        )
        return jsonify(resp), code
    
    except Exception as e:
        print(f"[EXCEPTION] list_cells: {e}")
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code
# OBTER CÉLULA
@cells_bp.route('/<int:cell_id>', methods=['GET'])
def get_cell(notebook_id, cell_id):
    try:
        user_id = _get_user_id()
        cell = CellService.get_cell(cell_id, user_id)
        
        if not cell or cell.notebook_id != notebook_id:
            resp, code = APIResponse.not_found("Célula")
            return jsonify(resp), code
        
        resp, code = APIResponse.success(data=serialize_model(cell))
        return jsonify(resp), code
    
    except Exception as e:
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code


# ATUALIZAR CÉLULA
@cells_bp.route('/<int:cell_id>', methods=['PUT'])
def update_cell(notebook_id, cell_id):
    """
    PUT /api/notebooks/{notebook_id}/cells/{cell_id}
    Body: campos a atualizar (cell_type, content, output, position, is_hidden, tags, sql_connection)
    """
    try:
        user_id = _get_user_id()
        cell = CellService.get_cell(cell_id, user_id)
        
        if not cell or cell.notebook_id != notebook_id:
            resp, code = APIResponse.not_found("Célula")
            return jsonify(resp), code
        
        data = request.get_json() or {}
        if not data:
            resp, code = APIResponse.bad_request("Nenhum dado para atualizar")
            return jsonify(resp), code
        
        # Converte 'code' para 'python' se presente
        if 'cell_type' in data and data['cell_type'] == 'code':
            data['cell_type'] = 'python'
        
        cell_updated, error = CellService.update_cell(
            cell_id=cell_id,
            user_id=user_id,
            **data
        )
        
        if error:
            resp, code = APIResponse.bad_request(error)
            return jsonify(resp), code
        
        resp, code = APIResponse.success(
            data=serialize_model(cell_updated),
            message="Célula atualizada"
        )
        return jsonify(resp), code
    
    except Exception as e:
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code


# DELETAR CÉLULA
@cells_bp.route('/<int:cell_id>', methods=['DELETE'])
def delete_cell(notebook_id, cell_id):
    try:
        user_id = _get_user_id()
        cell = CellService.get_cell(cell_id, user_id)
        
        if not cell or cell.notebook_id != notebook_id:
            resp, code = APIResponse.not_found("Célula")
            return jsonify(resp), code
        
        success, error = CellService.delete_cell(cell_id, user_id)
        
        if not success:
            resp, code = APIResponse.bad_request(error)
            return jsonify(resp), code
        
        resp, code = APIResponse.success(message="Célula deletada")
        return jsonify(resp), code
    
    except Exception as e:
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code


# ==========================================================
# EXECUTAR CÉLULA (via notebook context)
# ==========================================================

from app.executor.executor_service import CellExecutionService
import time

@cells_bp.route('/<int:cell_id>/execute', methods=['POST'])
def execute_cell_via_notebook(notebook_id, cell_id):
    """
    POST /api/notebooks/{notebook_id}/cells/{cell_id}/execute
    Executa uma célula pertencente ao notebook.
    """
    try:
        user_id = _get_user_id()
        
        # Verificar se a célula existe e pertence ao notebook e ao usuário
        cell = CellService.get_cell(cell_id, user_id)
        if not cell or cell.notebook_id != notebook_id:
            resp, code = APIResponse.not_found("Célula")
            return jsonify(resp), code
        
        # Executar
        start_time = time.time()
        result = CellExecutionService.execute_cell(cell)
        execution_time = round(time.time() - start_time, 4)
        
        if not isinstance(result, dict):
            resp, code = APIResponse.internal_error("Executor retornou resposta inválida")
            return jsonify(resp), code
        
        result["execution_time"] = execution_time
        result["cell_id"] = cell.id
        
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    
    except Exception as e:
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code

# REORDENAR CÉLULAS

@cells_bp.route('/reorder', methods=['POST'])
def reorder_cells(notebook_id):
    """
    POST /api/notebooks/{notebook_id}/cells/reorder
    Body: {"cell_order": [cell_id1, cell_id2, ...]}
    """
    try:
        user_id = _get_user_id()
        data = request.get_json() or {}
        
        validation = ValidateRequest.required_fields(data, ['cell_order'])
        if validation:
            return jsonify(validation[0]), validation[1]
        
        cell_order = data.get('cell_order')
        if not isinstance(cell_order, list):
            resp, code = APIResponse.bad_request("cell_order deve ser uma lista")
            return jsonify(resp), code
        
        success, error = CellService.reorder_cells(
            notebook_id=notebook_id,
            user_id=user_id,
            cell_order=cell_order
        )
        
        if not success:
            resp, code = APIResponse.bad_request(error)
            return jsonify(resp), code
        
        resp, code = APIResponse.success(message="Células reordenadas")
        return jsonify(resp), code
    
    except Exception as e:
        resp, code = APIResponse.internal_error(str(e))
        return jsonify(resp), code