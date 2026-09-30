"""
SQLite Adapter
Responsável por criar conexões SQLite seguras e reutilizáveis.
"""

import os
import sqlite3
from pathlib import Path


class SQLiteAdapter:

    @staticmethod
    def connect(db_path: str) -> sqlite3.Connection:
        """
        Cria conexão SQLite validando existência do arquivo.
        """

        if not db_path:
            raise ValueError("Caminho do banco de dados não informado.")

        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"Banco SQLite não encontrado: {db_path}"
            )

        # URI mode=ro prevents writes even if SQL validation misses a statement.
        db_file = Path(db_path).resolve(strict=True)
        conn = sqlite3.connect(f"{db_file.as_uri()}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")

        # Permite acesso por nome da coluna
        conn.row_factory = sqlite3.Row

        return conn