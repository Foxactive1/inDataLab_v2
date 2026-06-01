"""
Kernel Manager - Gerencia o estado (variáveis) de cada notebook.
Cada notebook tem seu próprio namespace de execução com isolamento básico.
Injeta automaticamente o dicionário _datasets com os arquivos enviados.
Captura a última expressão da célula (ex: df.head()) usando AST.
"""

import time
import threading
import json
import builtins
import io
import traceback
import logging
import ast
from contextlib import redirect_stdout
from typing import Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Configuração de logging
logger = logging.getLogger(__name__)

# ============================================================
# Constantes
# ============================================================
SESSION_TIMEOUT = 1800          # 30 minutos sem atividade -> limpar
CLEANUP_INTERVAL = 300          # 5 minutos entre limpezas
DEFAULT_EXECUTION_TIMEOUT = 30  # segundos
MAX_EXECUTION_TIMEOUT = 120     # limite máximo seguro

# Nomes de funções perigosas removidas do __builtins__
DANGEROUS_BUILTINS = {'open', 'eval', 'exec', 'compile', 'breakpoint', 'input'}

# ============================================================
# Estado global em memória
# ============================================================
_sessions: Dict[int, Dict[str, Any]] = {}      # notebook_id -> globals
_last_activity: Dict[int, float] = {}          # timestamp do último acesso

# Lock para acesso concorrente às estruturas
_state_lock = threading.RLock()


def _cleanup_expired() -> None:
    """Remove sessões inativas há mais de SESSION_TIMEOUT segundos."""
    now = time.time()
    with _state_lock:
        expired = [
            nid for nid, last in _last_activity.items()
            if now - last > SESSION_TIMEOUT
        ]
        for nid in expired:
            _sessions.pop(nid, None)
            _last_activity.pop(nid, None)
            logger.info(f"Sessão do notebook {nid} expirada e removida")


def _start_cleanup_thread() -> None:
    """Inicia thread daemon que limpa sessões periodicamente."""
    def cleaner():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            _cleanup_expired()
    threading.Thread(target=cleaner, daemon=True).start()


_start_cleanup_thread()


# ============================================================
# Namespace seguro
# ============================================================
def _create_safe_namespace(notebook_id: int) -> Dict[str, Any]:
    """
    Cria um dicionário a ser usado como namespace de execução.
    Remove funções perigosas do __builtins__ e define __name__.
    """
    safe_builtins = dict(vars(builtins))
    for dangerous in DANGEROUS_BUILTINS:
        safe_builtins.pop(dangerous, None)

    return {
        '__builtins__': safe_builtins,
        '__name__': f'notebook_{notebook_id}',
    }


def _load_datasets_into_session(notebook_id: int, session_dict: Dict[str, Any]) -> None:
    """
    Consulta o banco e insere o dicionário _datasets na sessão.
    Esta função é chamada sempre que a sessão é criada ou atualizada.
    """
    try:
        # Importação tardia para evitar ciclos
        from app.database.db import db
        from app.models.dataset import Dataset

        datasets = db.session.query(Dataset).filter_by(notebook_id=notebook_id).all()
        datasets_info = {}
        for ds in datasets:
            col_names = []
            if ds.column_names:
                try:
                    col_names = json.loads(ds.column_names or [])
                except json.JSONDecodeError:
                    logger.warning(f"Dataset {ds.id} tem column_names inválido")
            datasets_info[ds.filename] = {
                "id": ds.id,
                "filename": ds.filename,
                "path": ds.file_path,
                "file_type": ds.file_type,
                "rows": ds.rows,
                "columns": ds.columns,
                "column_names": col_names,
                "size_bytes": ds.file_size,
            }
        session_dict["_datasets"] = datasets_info
        logger.debug(f"Carregados {len(datasets_info)} datasets para notebook {notebook_id}")
    except Exception as e:
        logger.error(f"Erro ao carregar datasets para notebook {notebook_id}: {e}")
        session_dict["_datasets"] = {}


# ============================================================
# API pública
# ============================================================
def get_session(notebook_id: int) -> Dict[str, Any]:
    """
    Retorna o namespace (globals) do notebook.
    Cria um novo namespace se ainda não existir.
    """
    with _state_lock:
        _last_activity[notebook_id] = time.time()
        if notebook_id not in _sessions:
            _sessions[notebook_id] = _create_safe_namespace(notebook_id)
            _load_datasets_into_session(notebook_id, _sessions[notebook_id])
            logger.info(f"Nova sessão criada para notebook {notebook_id}")
        return _sessions[notebook_id]


def update_session(notebook_id: int, new_globals: Dict[str, Any]) -> None:
    """
    Atualiza o namespace com novos símbolos (ignora chaves começadas com '__').
    Útil para mesclar variáveis criadas em execuções que não usam o mesmo dict.
    """
    session = get_session(notebook_id)
    with _state_lock:
        for key, value in new_globals.items():
            if not key.startswith('__'):
                session[key] = value
        _last_activity[notebook_id] = time.time()


def refresh_datasets_in_session(notebook_id: int) -> None:
    """Recarrega a lista de datasets na sessão ativa (após upload/delete)."""
    with _state_lock:
        if notebook_id in _sessions:
            _load_datasets_into_session(notebook_id, _sessions[notebook_id])
            _last_activity[notebook_id] = time.time()
            logger.info(f"Datasets atualizados para notebook {notebook_id}")


def delete_session(notebook_id: int) -> None:
    """Remove a sessão do notebook (útil ao deletar o notebook)."""
    with _state_lock:
        _sessions.pop(notebook_id, None)
        _last_activity.pop(notebook_id, None)
        logger.info(f"Sessão do notebook {notebook_id} removida")


def list_session_variables(notebook_id: int) -> Dict[str, str]:
    """
    Retorna um resumo das variáveis atuais no namespace (para debug).
    Exclui __builtins__ e outras chaves internas.
    """
    session = get_session(notebook_id)
    with _state_lock:
        return {
            k: type(v).__name__
            for k, v in session.items()
            if not k.startswith('__')
        }


# ============================================================
# Execução com timeout e captura da última expressão
# ============================================================
def _execute_in_thread(code: str, namespace: Dict[str, Any],
                       result_holder: list, error_holder: list) -> None:
    """
    Executa código em thread separada, capturando stdout e o valor da última expressão.
    A última expressão é identificada via AST e avaliada separadamente.
    """
    stdout_buffer = io.StringIO()
    try:
        # Analisa o código para separar a última expressão
        tree = ast.parse(code)
        last_expr_code = None
        code_without_last = code

        if tree.body:
            last_node = tree.body[-1]
            if isinstance(last_node, ast.Expr):
                # A última linha é uma expressão solta (ex: df.head())
                try:
                    # Para Python 3.9+, extrai o código da última expressão
                    last_expr_code = ast.unparse(last_node.value)
                    # Reconstrói o código sem a última expressão
                    code_without_last = '\n'.join(
                        ast.unparse(node) for node in tree.body[:-1]
                    )
                except AttributeError:
                    # Fallback para versões anteriores (não suporta unparse)
                    # Executa tudo normalmente, não captura última expressão
                    last_expr_code = None
                    code_without_last = code

        with redirect_stdout(stdout_buffer):
            # Executa o código principal (sem a última expressão)
            if code_without_last.strip():
                exec(code_without_last, namespace)

            # Se havia uma última expressão, avalia e guarda no namespace
            if last_expr_code is not None:
                last_value = eval(last_expr_code, namespace)
                namespace['__last_expression__'] = last_value

        result_holder.append({
            'logs': stdout_buffer.getvalue(),
            'last_expression': namespace.pop('__last_expression__', None)
        })
    except Exception as e:
        error_holder.append((e, traceback.format_exc()))


def execute_code(code: str, notebook_id: int,
                 timeout_sec: int = DEFAULT_EXECUTION_TIMEOUT) -> Tuple[bool, Dict[str, Any]]:
    """
    Executa código Python no namespace persistente do notebook.
    Captura a última expressão (se existir) e retorna em 'last_expression'.

    Args:
        code: Código Python a ser executado
        notebook_id: ID do notebook (determina o namespace)
        timeout_sec: Tempo máximo de execução (segundos)

    Returns:
        Tuple (success, result_dict) onde:
            success: bool
            result_dict contém:
                - logs (str): saída padrão capturada
                - last_expression (Any): valor da última expressão (se houver)
                - execution_time (float): tempo total em segundos
                - error_message (str or None): mensagem de erro, se houver
    """
    start_time = time.perf_counter()
    namespace = get_session(notebook_id)

    output_capture = []
    error_capture = []

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        _execute_in_thread, code, namespace, output_capture, error_capture
    )

    try:
        future.result(timeout=timeout_sec)
        execution_time = time.perf_counter() - start_time
        exec_data = output_capture[0] if output_capture else {'logs': '', 'last_expression': None}
        logs = exec_data.get('logs', '')
        last_expr = exec_data.get('last_expression')

        with _state_lock:
            _last_activity[notebook_id] = time.time()

        return True, {
            'logs': logs,
            'last_expression': last_expr,
            'execution_time': execution_time,
            'error_message': None
        }

    except FutureTimeoutError:
        future.cancel()
        execution_time = time.perf_counter() - start_time
        error_msg = f"Execução cancelada após {timeout_sec} segundos (timeout)"
        logger.warning(f"Timeout na execução do notebook {notebook_id}: {error_msg}")
        return False, {
            'logs': f"ERRO: {error_msg}\n",
            'last_expression': None,
            'execution_time': execution_time,
            'error_message': error_msg
        }

    except Exception as e:
        execution_time = time.perf_counter() - start_time
        logs = ""
        if error_capture:
            exc, tb = error_capture[0]
            logs = tb
            error_msg = str(exc)
        else:
            error_msg = str(e)
            logs = traceback.format_exc()
        logger.debug(f"Erro na execução do notebook {notebook_id}: {error_msg}")
        return False, {
            'logs': logs,
            'last_expression': None,
            'execution_time': execution_time,
            'error_message': error_msg
        }

    finally:
        executor.shutdown(wait=False)