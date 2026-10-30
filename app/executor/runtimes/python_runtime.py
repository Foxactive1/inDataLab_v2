"""
Python Runtime do InDataLab.

Em produção, toda célula Python é executada no E2B Code Interpreter,
em uma microVM isolada do processo Flask. O runtime local antigo fica
disponível somente para desenvolvimento local sem E2B configurado.
"""

import io
import time
import base64
import traceback

import pandas as pd
from flask import current_app

from app.executor.runtimes.base import BaseRuntime
from app.executor.e2b_sandbox_service import E2BPythonSandboxService
from app.utils.json_utils import sanitize_json


class PythonRuntime(BaseRuntime):
    """Runtime Python com sessão persistente por notebook."""

    def execute(self, cell):
        started_at = time.perf_counter()

        # Em desenvolvimento local, preserva o fluxo anterior para facilitar
        # a edição do projeto sem exigir conta/chave E2B.
        if (
            not current_app.config.get("IS_PRODUCTION", False)
            and not current_app.config.get("E2B_API_KEY")
        ):
            return self._execute_local_development(cell, started_at)

        if not current_app.config.get("E2B_API_KEY"):
            return {
                "success": False,
                "error": (
                    "Sandbox Python não configurado: cadastre E2B_API_KEY "
                    "no ambiente do backend e habilite ENABLE_KERNELS."
                ),
                "execution_time": time.perf_counter() - started_at,
            }

        return E2BPythonSandboxService.execute(
            notebook_id=cell.notebook_id,
            code=cell.content,
        )

    def _execute_local_development(self, cell, started_at):
        """Fallback restrito a ambiente de desenvolvimento local."""
        try:
            from app.executor.kernel_manager import (
                refresh_datasets_in_session,
                execute_code,
            )

            notebook_id = cell.notebook_id
            refresh_datasets_in_session(notebook_id)

            success, exec_result = execute_code(
                code=cell.content,
                notebook_id=notebook_id,
                timeout_sec=30,
            )

            if not success:
                return {
                    "success": False,
                    "error": exec_result.get("error_message", "Erro desconhecido"),
                    "execution_time": exec_result.get(
                        "execution_time", time.perf_counter() - started_at
                    ),
                }

            logs = exec_result.get("logs", "")
            last = exec_result.get("last_expression")
            execution_time = exec_result.get(
                "execution_time", time.perf_counter() - started_at
            )

            if isinstance(last, pd.DataFrame):
                df_clean = last.where(pd.notnull(last), None)
                return {
                    "success": True,
                    "output": df_clean.to_string(index=False),
                    "output_json": sanitize_json(
                        df_clean.to_dict(orient="records")
                    ),
                    "rows_returned": len(df_clean),
                    "output_type": "table",
                    "execution_time": execution_time,
                    "logs": logs,
                }

            try:
                from plotly.basedatatypes import BaseFigure
                if isinstance(last, BaseFigure):
                    return {
                        "success": True,
                        "output": last.to_html(
                            full_html=False,
                            include_plotlyjs="cdn",
                        ),
                        "output_type": "html",
                        "execution_time": execution_time,
                        "logs": logs,
                    }
            except Exception:
                pass

            try:
                from matplotlib.figure import Figure
                if isinstance(last, Figure):
                    buffer = io.BytesIO()
                    last.savefig(buffer, format="png", bbox_inches="tight")
                    buffer.seek(0)
                    image_base64 = base64.b64encode(
                        buffer.read()
                    ).decode("ascii")
                    return {
                        "success": True,
                        "output": (
                            f'<img src="data:image/png;base64,{image_base64}" '
                            'class="img-fluid">'
                        ),
                        "output_type": "html",
                        "execution_time": execution_time,
                        "logs": logs,
                    }
            except Exception:
                pass

            return {
                "success": True,
                "output": repr(last) if last is not None else logs,
                "output_type": "text",
                "execution_time": execution_time,
                "logs": logs,
            }

        except Exception:
            return {
                "success": False,
                "error": traceback.format_exc(),
                "execution_time": time.perf_counter() - started_at,
            }
