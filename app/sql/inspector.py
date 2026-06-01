"""
Inspector SQLite
Responsável por inspecionar estrutura e metadados do banco.
"""

from typing import List, Dict, Any
from app.sql.sqlite_adapter import SQLiteAdapter


class DatabaseInspector:

    @staticmethod
    def list_tables(conn) -> List[str]:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def get_columns(conn, table_name: str) -> List[Dict[str, Any]]:

        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info(`{table_name}`)"
        )

        columns = []

        for col in cursor.fetchall():

            columns.append({
                "cid": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": bool(col[3]),
                "default_value": col[4],
                "pk": bool(col[5]),
            })

        return columns

    @staticmethod
    def get_row_count(conn, table_name: str) -> int:

        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM `{table_name}`"
        )

        return cursor.fetchone()[0]

    @staticmethod
    def get_sample_data(
        conn,
        table_name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:

        cursor = conn.cursor()

        columns = DatabaseInspector.get_columns(
            conn,
            table_name
        )

        column_names = [col["name"] for col in columns]

        cursor.execute(
            f"SELECT * FROM `{table_name}` LIMIT {limit}"
        )

        rows = cursor.fetchall()

        return [
            dict(zip(column_names, row))
            for row in rows
        ]

    @staticmethod
    def table_exists(conn, table_name: str) -> bool:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
            AND name=?
        """, (table_name,))

        return cursor.fetchone() is not None

    @staticmethod
    def inspect_database(db_path: str) -> Dict[str, Any]:

        conn = SQLiteAdapter.connect(db_path)

        try:

            tables = DatabaseInspector.list_tables(conn)

            result = {
                "database_path": db_path,
                "total_tables": len(tables),
                "tables": []
            }

            for table_name in tables:

                result["tables"].append({

                    "table_name": table_name,

                    "columns": DatabaseInspector.get_columns(
                        conn,
                        table_name
                    ),

                    "row_count": DatabaseInspector.get_row_count(
                        conn,
                        table_name
                    ),

                    "sample_data": DatabaseInspector.get_sample_data(
                        conn,
                        table_name
                    )
                })

            return result

        finally:
            conn.close()