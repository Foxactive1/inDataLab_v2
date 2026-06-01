"""
Módulo Blueprint para Copilot - Assistente IA para Notebooks Interativos

Fornece endpoints REST para chat interativo com o Copilot em contexto de notebook,
incluindo gerenciamento de conversas e acesso a datasets.

Autor: InNovaIdeia
Data: 2026
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Optional, Tuple, Any
from functools import wraps
import logging
import traceback
import os

# Modelos e Serviços
from app.services.ai_service import AIService
from app.models.notebook import Notebook
from app.models.cell import Cell
from app.models.user import User
from app.models.dataset import Dataset
from app.models.ai_conversation import AIConversation
from app.database.db import db

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

bp = Blueprint('copilot', __name__, url_prefix='/api/copilot')
logger = logging.getLogger(__name__)

# Constantes
DEFAULT_USER_NAME = "Usuário Padrão"
DEFAULT_USER_EMAIL = os.getenv('DEFAULT_COPILOT_USER_EMAIL', 'demo@indatalab.com')
SESSION_ID_PATTERN = "notebook_{notebook_id}"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MODEL = 'llama-3.3-70b-versatile'
MAX_OUTPUT_PREVIEW = 1000
TRACEBACK_IN_RESPONSE = os.getenv('FLASK_ENV', 'production') != 'production'

# ============================================================================
# DECORADORES
# ============================================================================

def handle_database_errors(f):
    """Decorator para rollback automático em caso de erro de banco."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error in {f.__name__}: {str(e)}")
            raise
    return decorated_function

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_or_create_default_user() -> User:
    """
    Obtém ou cria um usuário padrão para operações do Copilot.
    
    Returns:
        User: Instância do usuário padrão ativo.
        
    Raises:
        Exception: Se houver erro ao criar ou recuperar usuário.
    """
    try:
        user = User.query.filter_by(is_active=True).first()
        
        if not user:
            user = User(
                name=DEFAULT_USER_NAME,
                email=DEFAULT_USER_EMAIL,
                # IMPORTANTE: Em produção, usar hash seguro via werkzeug.security
                password_hash="__placeholder__",
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"Usuário padrão criado com ID: {user.id} ({DEFAULT_USER_EMAIL})")
        
        return user
    
    except Exception as e:
        db.session.rollback()
        logger.critical(f"Falha ao obter/criar usuário padrão: {str(e)}")
        raise


def get_notebook_context(notebook_id: int, user_id: int) -> str:
    """
    Constrói contexto completo do notebook para o Copilot, incluindo:
    - Metadados do notebook
    - Lista de datasets disponíveis
    - Células (código e markdown) com saídas
    
    Args:
        notebook_id: ID do notebook.
        user_id: ID do usuário (para validação de permissão).
    
    Returns:
        str: Contexto formatado em Markdown para prompt do Copilot.
        
    Raises:
        ValueError: Se notebook não for encontrado ou sem permissão.
    """
    # Validação de permissão
    notebook = Notebook.query.filter_by(
        id=notebook_id, 
        user_id=user_id
    ).first()
    
    if not notebook:
        raise ValueError("Notebook não encontrado ou sem permissão.")
    
    context_lines = [
        f"# Notebook: {notebook.title}\n",
    ]
    
    # Descrição
    if notebook.description:
        context_lines.append(f"Descrição: {notebook.description}\n")
    
    context_lines.append(f"Kernel: {notebook.kernel_type}\n")
    
    # ========== DATASETS ==========
    datasets = Dataset.query.filter_by(notebook_id=notebook_id).all()
    context_lines.append("\n## Datasets disponíveis neste notebook:\n")
    
    if datasets:
        for ds in datasets:
            context_lines.append(
                f"- **{ds.filename}** "
                f"(tipo: {ds.file_type}, {ds.rows} linhas, {ds.columns} colunas)\n"
            )
            
            # Colunas (se disponível)
            if ds.column_names:
                try:
                    import json
                    cols = json.loads(ds.column_names)
                    cols_preview = ', '.join(cols[:10])
                    if len(cols) > 10:
                        cols_preview += "..."
                    context_lines.append(f"  Colunas: {cols_preview}\n")
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Falha ao parsear colunas do dataset {ds.id}")
            
            context_lines.append(f"  Caminho: `{ds.file_path}`\n")
    else:
        context_lines.append("Nenhum dataset anexado ainda.\n")
    
    # ========== CÉLULAS ==========
    cells = Cell.query.filter_by(notebook_id=notebook_id).order_by(
        Cell.position.asc()
    ).all()
    
    context_lines.append("\n## Células do Notebook:\n")
    
    for idx, cell in enumerate(cells, 1):
        context_lines.append(f"\n### Célula {idx} - {cell.cell_type}\n")
        context_lines.append(f"```{cell.cell_type}\n{cell.content}\n```\n")
        
        # Output (apenas para células de código)
        if cell.output and cell.cell_type == 'code':
            output_preview = cell.output[:MAX_OUTPUT_PREVIEW]
            if len(cell.output) > MAX_OUTPUT_PREVIEW:
                output_preview += "…"
            context_lines.append(f"**Saída:**\n```\n{output_preview}\n```\n")
    
    return "".join(context_lines)


def build_system_prompt(notebook_context: str) -> str:
    """
    Constrói o system prompt para o Copilot com contexto do notebook.
    
    Args:
        notebook_context: Contexto formatado do notebook.
    
    Returns:
        str: System prompt completo.
    """
    return f"""Você é um assistente de IA especializado em notebooks interativos (como Jupyter/InDataLab).

# Contexto Atual
{notebook_context}

# Instruções

1. **Resposta ao Contexto**: Responda perguntas sobre código, dados e saídas do notebook.
2. **Sugestões de Código**: Sugira melhorias, correções ou novas células (Python ou Markdown).
3. **Formatação**: Use blocos markdown com linguagem especificada (```python ou ```markdown).
4. **Precisão**: Seja conciso e direto. Não invente dados fora do contexto.
5. **Inserção de Células**: Ao sugerir código, indique claramente onde inseri-lo.
6. **Segurança**: Nunca execute código no sistema real; apenas dê instruções.

# Variáveis Disponíveis

No ambiente Python, datasets estão acessíveis via `_datasets` (dicionário):
- Chave: nome do arquivo
- Valor: dict com 'path', 'file_type', 'rows', 'columns', 'column_names'

Exemplo:
```python
import pandas as pd
df = pd.read_csv(_datasets['dados.csv']['path'])
df.head()
```
"""


# ============================================================================
# ENDPOINTS
# ============================================================================

@bp.route('/notebooks/<int:notebook_id>/chat', methods=['POST'])
@handle_database_errors
def copilot_chat(notebook_id: int) -> Tuple[Any, int]:
    """
    Endpoint para chat com o Copilot em contexto de notebook.
    
    **Método**: POST
    **URL**: `/api/copilot/notebooks/<notebook_id>/chat`
    
    **Payload JSON**:
    ```json
    {
      "message": "Como faço para visualizar as primeiras linhas?",
      "session_id": "opcional-notebook-session-abc123"
    }
    ```
    
    **Resposta (Sucesso 200)**:
    ```json
    {
      "success": true,
      "response": "Você pode usar...",
      "message_id": "msg_xyz",
      "tokens": {"input": 150, "output": 75}
    }
    ```
    
    **Resposta (Erro)**:
    ```json
    {
      "success": false,
      "error": "Descrição do erro"
    }
    ```
    
    Args:
        notebook_id: ID do notebook.
    
    Returns:
        Tuple[dict, int]: (Response JSON, HTTP Status Code)
    """
    try:
        # ========== VALIDAÇÃO ==========
        
        # Dados de entrada
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False, 
                'error': 'Requisição inválida: corpo vazio'
            }), 400
        
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({
                'success': False, 
                'error': 'Campo "message" vazio ou ausente'
            }), 400
        
        conversation_session_id = data.get('session_id')
        if not conversation_session_id:
            conversation_session_id = SESSION_ID_PATTERN.format(
                notebook_id=notebook_id
            )
        
        # Usuário
        user = get_or_create_default_user()
        user_id = user.id
        
        # Notebook (verificação de permissão)
        notebook = Notebook.query.filter_by(
            id=notebook_id, 
            user_id=user_id
        ).first()
        
        if not notebook:
            logger.warning(
                f"Acesso negado ao notebook {notebook_id} para user {user_id}"
            )
            return jsonify({
                'success': False, 
                'error': 'Notebook não encontrado ou sem permissão'
            }), 404
        
        # ========== CONSTRUÇÃO DE CONTEXTO ==========
        
        try:
            notebook_context = get_notebook_context(notebook_id, user_id)
        except ValueError as e:
            return jsonify({
                'success': False, 
                'error': str(e)
            }), 404
        
        system_prompt = build_system_prompt(notebook_context)
        
        # ========== CHAMADA À IA ==========
        
        ai_service = AIService()
        result = ai_service.chat_completion(
            user_id=user_id,
            content=user_message,
            notebook_id=notebook_id,
            conversation_session_id=conversation_session_id,
            system_prompt=system_prompt,
            temperature=DEFAULT_TEMPERATURE,
            model=DEFAULT_MODEL
        )
        
        if not result.get('success'):
            error_msg = result.get('error', 'Erro desconhecido do AIService')
            logger.error(f"AIService error: {error_msg}")
            return jsonify({
                'success': False, 
                'error': error_msg
            }), 500
        
        # ========== RESPOSTA BEM-SUCEDIDA ==========
        
        return jsonify({
            'success': True,
            'response': result.get('content', ''),
            'message_id': result.get('message_id'),
            'tokens': result.get('tokens', {})
        }), 200
    
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Erro no copilot_chat (notebook {notebook_id}): {str(e)}\n{error_trace}")
        
        response_body = {
            'success': False,
            'error': 'Erro interno do servidor'
        }
        
        # Em desenvolvimento, incluir traceback
        if TRACEBACK_IN_RESPONSE:
            response_body['traceback'] = error_trace
        
        return jsonify(response_body), 500


@bp.route('/notebooks/<int:notebook_id>/clear_chat', methods=['DELETE'])
@handle_database_errors
def clear_chat(notebook_id: int) -> Tuple[Any, int]:
    """
    Apaga todo o histórico de conversação do Copilot para um notebook.
    
    **Método**: DELETE
    **URL**: `/api/copilot/notebooks/<notebook_id>/clear_chat`
    
    **Resposta (Sucesso 200)**:
    ```json
    {
      "success": true,
      "deleted": 42,
      "message": "42 mensagens removidas"
    }
    ```
    
    **Resposta (Erro)**:
    ```json
    {
      "success": false,
      "error": "Descrição do erro"
    }
    ```
    
    Args:
        notebook_id: ID do notebook.
    
    Returns:
        Tuple[dict, int]: (Response JSON, HTTP Status Code)
    """
    try:
        user = get_or_create_default_user()
        session_id = SESSION_ID_PATTERN.format(notebook_id=notebook_id)
        
        # Verificar se notebook existe e pertence ao usuário
        notebook = Notebook.query.filter_by(
            id=notebook_id,
            user_id=user.id
        ).first()
        
        if not notebook:
            return jsonify({
                'success': False,
                'error': 'Notebook não encontrado'
            }), 404
        
        # Deletar conversações
        deleted_count = AIConversation.query.filter_by(
            conversation_session_id=session_id,
            user_id=user.id
        ).delete()
        
        db.session.commit()
        
        logger.info(
            f"Histórico limpo: {deleted_count} mensagens removidas "
            f"(notebook {notebook_id}, user {user.id})"
        )
        
        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'message': f'{deleted_count} mensagens removidas'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        error_trace = traceback.format_exc()
        logger.error(f"Erro ao limpar chat do notebook {notebook_id}: {str(e)}\n{error_trace}")
        
        response_body = {
            'success': False,
            'error': 'Erro ao limpar histórico'
        }
        
        if TRACEBACK_IN_RESPONSE:
            response_body['traceback'] = error_trace
        
        return jsonify(response_body), 500


# ============================================================================
# HEALTH CHECK (Opcional)
# ============================================================================

@bp.route('/health', methods=['GET'])
def health_check() -> Tuple[Dict[str, bool], int]:
    """
    Verifica saúde do serviço Copilot.
    
    Returns:
        Tuple[dict, int]: ({'status': 'ok'}, 200)
    """
    return jsonify({'status': 'ok'}), 200
