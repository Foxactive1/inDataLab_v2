"""
Python Runtime - Executa células Python do InDataLab.

Suporta:
- Python puro
- Pandas DataFrame
- Plotly
- Matplotlib
- stdout (print)
- Captura da última expressão estilo Jupyter
"""

import io
import time
import base64
import traceback

import pandas as pd

from app.executor.runtimes.base import BaseRuntime
from app.executor.kernel_manager import (
    refresh_datasets_in_session,
    execute_code,
)
from app.utils.json_utils import sanitize_json


class PythonRuntime(BaseRuntime):
    """
    Runtime Python com comportamento semelhante ao Jupyter Notebook.
    """

    def execute(self, cell):
        started_at = time.perf_counter()

        try:
            notebook_id = cell.notebook_id

            # Atualiza _datasets
            refresh_datasets_in_session(notebook_id)

            success, exec_result = execute_code(
                code=cell.content,
                notebook_id=notebook_id,
                timeout_sec=30,
            )

            if not success:
                return {
                    "success": False,
                    "error": exec_result.get(
                        "error_message",
                        "Erro desconhecido"
                    ),
                    "execution_time": exec_result.get(
                        "execution_time",
                        0
                    ),
                }

            logs = exec_result.get("logs", "")
            last = exec_result.get("last_expression")
            execution_time = exec_result.get("execution_time", 0)

            # =====================================================
            # DATAFRAME
            # =====================================================

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
                }

            # =====================================================
            # PLOTLY
            # =====================================================

            try:
                from plotly.basedatatypes import BaseFigure

                if isinstance(last, BaseFigure):

                    html = last.to_html(
                        full_html=False,
                        include_plotlyjs="cdn"
                    )

                    return {
                        "success": True,
                        "output": html,
                        "output_type": "html",
                        "execution_time": execution_time,
                    }

            except Exception:
                pass

            # =====================================================
            # MATPLOTLIB
            # =====================================================

            try:
                from matplotlib.figure import Figure

                if isinstance(last, Figure):

                    buffer = io.BytesIO()

                    last.savefig(
                        buffer,
                        format="png",
                        bbox_inches="tight"
                    )

                    buffer.seek(0)

                    image_base64 = base64.b64encode(
                        buffer.read()
                    ).decode("utf-8")

                    html = (
                        f'<img src="data:image/png;base64,{image_base64}" '
                        f'class="img-fluid">'
                    )

                    return {
                        "success": True,
                        "output": html,
                        "output_type": "html",
                        "execution_time": execution_time,
                    }

            except Exception:
                pass

            # =====================================================
            # OUTROS OBJETOS
            # =====================================================

            if last is not None:

                return {
                    "success": True,
                    "output": repr(last),
                    "output_type": "text",
                    "execution_time": execution_time,
                }

            # =====================================================
            # PRINTS / LOGS
            # =====================================================

            return {
                "success": True,
                "output": logs,
                "output_type": "text",
                "execution_time": execution_time,
            }

        except Exception:

            return {
                "success": False,
                "error": traceback.format_exc(),
                "execution_time":
                    time.perf_counter() - started_at,
            }