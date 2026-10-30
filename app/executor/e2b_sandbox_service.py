"""
E2B sandbox adapter for InDataLab.

Python code is executed by E2B Code Interpreter in a dedicated microVM.
The Flask process never evaluates submitted notebook code.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import current_app
from werkzeug.utils import secure_filename

from app.database.db import db
from app.models.dataset import Dataset
from app.models.notebook import Notebook
from app.utils.json_utils import sanitize_json

logger = logging.getLogger(__name__)

_LOCKS: dict[int, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _notebook_lock(notebook_id: int) -> threading.RLock:
    """Serialize executions for a notebook within this Flask worker."""
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(notebook_id, threading.RLock())


def _clip(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[saída truncada pelo InDataLab]"


def _column_names(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value[:100]]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed[:100]]
        except (TypeError, ValueError):
            pass
    return []


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class E2BPythonSandboxService:
    """Create, reuse and execute Python code inside E2B microVM sandboxes."""

    @staticmethod
    def _sdk():
        try:
            from e2b import (
                NotFoundException,
                SandboxNotFoundException,
                SandboxNotRunningException,
            )
            from e2b_code_interpreter import Sandbox
        except ImportError as exc:
            raise RuntimeError(
                "SDK E2B não instalado. Instale e2b-code-interpreter."
            ) from exc
        return Sandbox, (
            NotFoundException,
            SandboxNotFoundException,
            SandboxNotRunningException,
        )

    @staticmethod
    def _get_or_create_sandbox(notebook: Notebook):
        api_key = current_app.config.get("E2B_API_KEY")
        if not api_key:
            raise RuntimeError(
                "E2B_API_KEY não configurada no Render. "
                "Cadastre a chave no ambiente antes de habilitar ENABLE_KERNELS."
            )

        Sandbox, not_found_errors = E2BPythonSandboxService._sdk()
        ttl = int(current_app.config["E2B_SANDBOX_TIMEOUT"])

        if notebook.e2b_sandbox_id:
            try:
                sandbox = Sandbox.connect(
                    notebook.e2b_sandbox_id,
                    timeout=ttl,
                    api_key=api_key,
                )
                if sandbox.is_running():
                    sandbox.set_timeout(ttl)
                    notebook.e2b_sandbox_expires_at = (
                        datetime.utcnow() + timedelta(seconds=ttl)
                    )
                    db.session.commit()
                    return sandbox
            except not_found_errors:
                logger.info(
                    "Sandbox E2B expirado ou removido; criando outro. notebook_id=%s",
                    notebook.id,
                )

            # Um sandbox expirado não deve bloquear novas execuções.
            notebook.e2b_sandbox_id = None
            notebook.e2b_sandbox_expires_at = None
            db.session.flush()

        sandbox = Sandbox.create(
            timeout=ttl,
            api_key=api_key,
            allow_internet_access=False,
            metadata={
                "application": "indatalab",
                "notebook_id": str(notebook.id),
            },
        )

        notebook.e2b_sandbox_id = sandbox.sandbox_id
        notebook.e2b_sandbox_expires_at = (
            datetime.utcnow() + timedelta(seconds=ttl)
        )
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            try:
                sandbox.kill()
            except Exception:
                logger.exception("Falha ao encerrar sandbox sem registro no banco")
            raise

        logger.info(
            "Sandbox E2B criado. notebook_id=%s sandbox_id=%s",
            notebook.id,
            sandbox.sandbox_id,
        )
        return sandbox

    @staticmethod
    def _sync_datasets(sandbox, notebook_id: int) -> dict[str, dict[str, Any]]:
        """
        Copy notebook datasets into the remote sandbox.

        Paths include the content hash, so replacing a dataset creates a new
        remote path and avoids reading a stale copy in the persistent kernel.
        """
        datasets_info: dict[str, dict[str, Any]] = {}
        max_bytes = int(current_app.config["E2B_MAX_DATASET_BYTES"])
        remote_root = f"/home/user/indatalab_datasets/{notebook_id}"

        for dataset in Dataset.query.filter_by(notebook_id=notebook_id).all():
            local_path = Path(dataset.file_path)
            if not local_path.is_file():
                raise RuntimeError(
                    f"Arquivo do dataset '{dataset.filename}' não está disponível "
                    "no armazenamento do backend. Verifique o armazenamento persistente."
                )

            file_size = local_path.stat().st_size
            if file_size > max_bytes:
                raise RuntimeError(
                    f"Dataset '{dataset.filename}' excede o limite de "
                    f"{max_bytes // (1024 * 1024)} MB para sincronização com o sandbox."
                )

            digest = _sha256_file(local_path)
            safe_name = secure_filename(dataset.filename) or f"dataset_{dataset.id}"
            remote_path = (
                f"{remote_root}/{dataset.id}-{digest[:16]}-{safe_name}"
            )

            if not sandbox.files.exists(remote_path):
                with local_path.open("rb") as file_stream:
                    sandbox.files.write(remote_path, file_stream)

            datasets_info[dataset.filename] = {
                "id": dataset.id,
                "filename": dataset.filename,
                "path": remote_path,
                "file_type": dataset.file_type,
                "rows": dataset.rows,
                "columns": dataset.columns,
                "column_names": _column_names(dataset.column_names),
                "size_bytes": file_size,
            }

        return datasets_info

    @staticmethod
    def _build_code(datasets_info: dict[str, dict[str, Any]], code: str) -> str:
        """Inject the remote _datasets map without interpolating user strings as code."""
        serialized = json.dumps(datasets_info, ensure_ascii=False, default=str)
        prelude = (
            "import json as __indatalab_json\n"
            f"_datasets = __indatalab_json.loads({serialized!r})\n"
        )
        return prelude + "\n" + code

    @staticmethod
    def _normalise_execution(execution, elapsed: float) -> dict[str, Any]:
        max_output = int(current_app.config["E2B_MAX_OUTPUT_CHARS"])
        stdout = "\n".join(execution.logs.stdout or [])
        stderr = "\n".join(execution.logs.stderr or [])

        if execution.error:
            error = (
                f"{execution.error.name}: {execution.error.value}\n"
                f"{execution.error.traceback}"
            )
            return {
                "success": False,
                "error": _clip(error, max_output),
                "logs": _clip(stdout + ("\n" + stderr if stderr else ""), max_output),
                "output_type": "error",
                "execution_time": elapsed,
            }

        results = execution.results or []
        primary = next(
            (item for item in reversed(results) if item.is_main_result),
            results[-1] if results else None,
        )

        result: dict[str, Any] = {
            "success": True,
            "output": "",
            "output_type": "text",
            "logs": _clip(stdout + ("\n" + stderr if stderr else ""), max_output),
            "execution_time": elapsed,
        }

        if primary is None:
            result["output"] = _clip(stdout or "Execução concluída sem saída.", max_output)
            return result

        # Code Interpreter may return several representations for the same object.
        # Prefer structured data when available and retain rich output for the UI.
        structured = primary.json if primary.json is not None else primary.data
        if structured is not None:
            safe_data = sanitize_json(structured)
            encoded = json.dumps(safe_data, ensure_ascii=False, default=str)
            if len(encoded) <= max_output:
                result["output_json"] = safe_data
            result["output"] = _clip(primary.text or encoded, max_output)
            result["output_type"] = "table" if primary.html else "json"

        if primary.html:
            result["output"] = _clip(primary.html, max_output)
            result["output_type"] = "table" if structured is not None else "html"
        elif primary.png:
            result["output"] = _clip(
                '<img class="img-fluid" alt="Gráfico gerado no sandbox" '
                f'src="data:image/png;base64,{primary.png}">',
                max_output,
            )
            result["output_type"] = "html"
        elif primary.jpeg:
            result["output"] = _clip(
                '<img class="img-fluid" alt="Imagem gerada no sandbox" '
                f'src="data:image/jpeg;base64,{primary.jpeg}">',
                max_output,
            )
            result["output_type"] = "html"
        elif primary.svg:
            import base64

            encoded_svg = base64.b64encode(primary.svg.encode("utf-8")).decode("ascii")
            result["output"] = _clip(
                '<img class="img-fluid" alt="Gráfico SVG gerado no sandbox" '
                f'src="data:image/svg+xml;base64,{encoded_svg}">',
                max_output,
            )
            result["output_type"] = "html"
        elif primary.chart is not None:
            chart_data = primary.chart.to_dict()
            result["output_json"] = sanitize_json(chart_data)
            result["output"] = _clip(
                json.dumps(result["output_json"], ensure_ascii=False, default=str),
                max_output,
            )
            result["output_type"] = "chart"
        elif primary.markdown:
            result["output"] = _clip(primary.markdown, max_output)
            result["output_type"] = "markdown"
        elif primary.text:
            result["output"] = _clip(primary.text, max_output)
            result["output_type"] = "text"

        if primary.data is not None and isinstance(primary.data, (list, dict)):
            safe_data = sanitize_json(primary.data)
            encoded_data = json.dumps(
                safe_data, ensure_ascii=False, default=str
            )
            if len(encoded_data) <= max_output:
                result["output_json"] = safe_data
                result["rows_returned"] = (
                    len(safe_data) if isinstance(safe_data, list) else None
                )

        return result

    @classmethod
    def execute(cls, notebook_id: int, code: str) -> dict[str, Any]:
        started = time.perf_counter()
        if not code or not code.strip():
            return {"success": False, "error": "Código Python vazio."}

        if len(code.encode("utf-8")) > 256 * 1024:
            return {"success": False, "error": "Código excede o limite de 256 KB."}

        with _notebook_lock(notebook_id):
            try:
                notebook = (
                    Notebook.query.filter_by(id=notebook_id)
                    .with_for_update()
                    .first()
                )
                if notebook is None:
                    return {"success": False, "error": "Notebook não encontrado."}

                sandbox = cls._get_or_create_sandbox(notebook)
                datasets_info = cls._sync_datasets(sandbox, notebook_id)

                timeout = int(current_app.config["E2B_EXECUTION_TIMEOUT"])
                remote_code = cls._build_code(datasets_info, code)
                execution = sandbox.run_code(
                    remote_code,
                    timeout=timeout,
                    request_timeout=timeout + 20,
                )

                elapsed = time.perf_counter() - started
                return cls._normalise_execution(execution, elapsed)

            except Exception as exc:
                db.session.rollback()
                logger.exception(
                    "Falha na execução Python isolada. notebook_id=%s",
                    notebook_id,
                )
                return {
                    "success": False,
                    "error": (
                        "Não foi possível executar a célula no sandbox E2B: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    "execution_time": time.perf_counter() - started,
                }

    @classmethod
    def get_variables(cls, notebook_id: int) -> list[dict[str, Any]]:
        """Return names/types and small DataFrame previews for the AI assistant."""
        with _notebook_lock(notebook_id):
            try:
                notebook = Notebook.query.filter_by(id=notebook_id).first()
                if not notebook or not notebook.e2b_sandbox_id:
                    return []

                if not current_app.config.get("E2B_API_KEY"):
                    return []

                Sandbox, _ = cls._sdk()
                sandbox = Sandbox.connect(
                    notebook.e2b_sandbox_id,
                    timeout=int(current_app.config["E2B_SANDBOX_TIMEOUT"]),
                    api_key=current_app.config["E2B_API_KEY"],
                )
                code = '''
import json as __indatalab_json
__indatalab_items = []
for __indatalab_name, __indatalab_value in list(globals().items()):
    if __indatalab_name.startswith("_"):
        continue
    __indatalab_item = {
        "name": __indatalab_name,
        "type": type(__indatalab_value).__name__,
    }
    if hasattr(__indatalab_value, "columns") and hasattr(__indatalab_value, "head"):
        try:
            __indatalab_item["columns"] = [str(x) for x in list(__indatalab_value.columns)[:20]]
            __indatalab_item["preview"] = __indatalab_value.head(2).to_dict(orient="records")
            __indatalab_item["shape"] = list(__indatalab_value.shape)
        except Exception:
            pass
    __indatalab_items.append(__indatalab_item)
print(__indatalab_json.dumps(__indatalab_items, default=str))
'''
                execution = sandbox.run_code(code, timeout=10, request_timeout=20)
                if execution.error:
                    return []
                output = "\n".join(execution.logs.stdout or []).strip()
                parsed = json.loads(output) if output else []
                return parsed if isinstance(parsed, list) else []
            except Exception:
                logger.exception(
                    "Não foi possível consultar variáveis do sandbox. notebook_id=%s",
                    notebook_id,
                )
                return []

    @classmethod
    def close_notebook_sandbox(cls, notebook: Notebook) -> None:
        """Best-effort cleanup when a notebook is permanently deleted."""
        sandbox_id = getattr(notebook, "e2b_sandbox_id", None)
        if not sandbox_id:
            return
        try:
            Sandbox, _ = cls._sdk()
            Sandbox.kill(
                sandbox_id,
                api_key=current_app.config.get("E2B_API_KEY"),
            )
        except Exception:
            logger.exception(
                "Falha ao encerrar sandbox do notebook %s",
                notebook.id,
            )
        notebook.e2b_sandbox_id = None
        notebook.e2b_sandbox_expires_at = None
