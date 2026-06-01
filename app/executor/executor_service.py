"""
Service: CellExecutionService
Runtime principal do InDataLab – executa células com persistência de estado
"""

from datetime import datetime, timezone

from app.database.db import db

from app.models.cell import Cell
from app.models.execution import Execution

from app.executor.runtimes.python_runtime import PythonRuntime
from app.executor.runtimes.sql_runtime import SQLRuntime
from app.executor.runtimes.ai_runtime import AIRuntime

from app.utils.json_utils import sanitize_json


class CellExecutionService:
    """
    Serviço de execução de células com suporte a:
    - Python
    - SQL
    - AI
    - Markdown
    """

    RUNTIMES = {
        "python": PythonRuntime(),
        "sql": SQLRuntime(),
        "ai": AIRuntime(),
        "markdown": None,
    }

    @staticmethod
    def execute_cell(cell: Cell) -> dict:
        """
        Executa uma célula conforme seu tipo.
        """

        if cell.cell_type == "markdown":
            return CellExecutionService._execute_markdown(cell)

        runtime = CellExecutionService.RUNTIMES.get(
            cell.cell_type
        )

        if not runtime:
            return {
                "success": False,
                "error": (
                    f"Runtime não suportado "
                    f"para tipo: {cell.cell_type}"
                )
            }

        result = runtime.execute(cell)

        try:

            if result.get("success"):

                cell.status = "success"

                cell.output_type = result.get(
                    "output_type",
                    "text"
                )

                # ==========================================
                # PRIORIDADE DE SAÍDA
                # ==========================================

                if "image_path" in result:

                    cell.output = str(
                        result["image_path"]
                    )

                    cell.output_type = "image_path"

                elif "html_path" in result:

                    cell.output = str(
                        result["html_path"]
                    )

                    cell.output_type = "html_path"

                elif "image" in result:

                    cell.output = str(
                        result["image"]
                    )

                    cell.output_type = "image"

                elif "html" in result:

                    cell.output = str(
                        result["html"]
                    )

                    cell.output_type = "html"

                else:

                    cell.output = str(
                        result.get(
                            "output",
                            ""
                        )
                    )

                # ==========================================
                # JSON SEGURO
                # ==========================================

                if "output_json" in result:

                    cell.output_json = sanitize_json(
                        result["output_json"]
                    )

                if "rows_returned" in result:

                    cell.rows_returned = int(
                        result["rows_returned"]
                    )

                cell.error_output = None

            else:

                cell.status = "error"

                cell.error_output = str(
                    result.get(
                        "error",
                        ""
                    )
                )

                cell.output = str(
                    result.get(
                        "error",
                        ""
                    )
                )

                cell.output_type = "error"

            # ==========================================
            # HISTÓRICO DE EXECUÇÃO
            # ==========================================

            execution = Execution(
                cell_id=cell.id,
                status=cell.status,
                logs=str(
                    result.get(
                        "output",
                        ""
                    )
                ),
                error_message=str(
                    result.get(
                        "error",
                        ""
                    )
                ) if result.get("error") else None,
                execution_time=float(
                    result.get(
                        "execution_time",
                        0
                    )
                ),
                executed_at=datetime.now(
                    timezone.utc
                )
            )

            db.session.add(execution)

            cell.execution_count = (
                cell.execution_count or 0
            ) + 1

            cell.last_executed_at = (
                datetime.now(timezone.utc)
            )

            db.session.commit()

        except Exception:
            db.session.rollback()
            raise

        return result

    @staticmethod
    def _execute_markdown(cell: Cell) -> dict:
        """
        Execução para markdown.
        """

        cell.status = "success"
        cell.output = cell.content
        cell.output_type = "markdown"

        return {
            "success": True,
            "output": cell.content,
            "output_type": "markdown"
        }