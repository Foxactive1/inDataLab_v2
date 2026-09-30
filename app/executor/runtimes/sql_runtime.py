"""
SQL Runtime
Executa queries SQL em datasets SQLite.
"""

import time
from pathlib import Path

from app.models.dataset import Dataset
import pandas as pd

from app.executor.runtimes.base import BaseRuntime
from app.sql.sqlite_adapter import SQLiteAdapter
from app.sql.validators import validate_sql_query

from app.utils.json_utils import sanitize_json


class SQLRuntime(BaseRuntime):

    def execute(self, cell):

        started_at = time.perf_counter()

        try:

            validation = validate_sql_query(
                cell.content
            )

            if not validation["valid"]:

                return {
                    "success": False,
                    "error": validation["error"],
                    "execution_time":
                        time.perf_counter() - started_at
                }

            connection_str = self._resolve_connection(
                cell
            )

            conn = SQLiteAdapter.connect(
                connection_str
            )

            try:

                df = pd.read_sql(
                    cell.content,
                    conn
                )

            finally:
                conn.close()

            records = sanitize_json(
                df.to_dict(
                    orient="records"
                )
            )

            return {
                "success": True,
                "output": df.to_string(index=False),
                "output_json": records,
                "rows_returned": len(df),
                "execution_time":
                    time.perf_counter() - started_at,
                "output_type": "table"
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
                "execution_time":
                    time.perf_counter() - started_at
            }

    def _resolve_connection(self, cell):
        """Apenas SQLite cadastrado como dataset do próprio notebook."""
        candidate = (
            getattr(cell, "sql_connection", None)
            or (cell.dataset_ref.file_path if getattr(cell, "dataset_ref", None) else None)
            or (cell.notebook.default_sql_connection if getattr(cell, "notebook", None) else None)
        )
        if not candidate:
            raise ValueError("Nenhuma conexão SQL configurada.")

        target = Path(candidate).resolve(strict=True)
        datasets = Dataset.query.filter_by(notebook_id=cell.notebook_id).all()
        allowed = any(
            (ds.file_type == "db" or ds.is_sql_database)
            and Path(ds.file_path).resolve(strict=False) == target
            for ds in datasets
        )
        if not allowed:
            raise PermissionError("Conexão SQL não pertence aos datasets SQLite deste notebook.")
        return str(target)
