"""
SQL Runtime
Executa queries SQL em datasets SQLite.
"""

import time
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

        if getattr(cell, "sql_connection", None):
            return cell.sql_connection

        if getattr(cell, "dataset_ref", None):
            return cell.dataset_ref.file_path

        if (
            getattr(cell, "notebook", None)
            and cell.notebook.default_sql_connection
        ):
            return cell.notebook.default_sql_connection

        raise ValueError(
            "Nenhuma conexão SQL configurada."
        )