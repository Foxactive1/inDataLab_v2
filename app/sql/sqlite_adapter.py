"""
SQLite Adapter
Responsável por criar conexões SQLite seguras e reutilizáveis.
"""

import os
import sqlite3


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

        conn = sqlite3.connect(db_path)

        # Permite acesso por nome da coluna
        conn.row_factory = sqlite3.Row

        return conn