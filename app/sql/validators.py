"""
SQL Validators
Validação e segurança de queries SQL
"""

import re


BLOCKED_KEYWORDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "ALTER",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX"
]


def validate_sql_query(query: str):
    """
    Validar segurança da query SQL.

    Permite apenas operações seguras.
    """

    if not query:

        return {
            "valid": False,
            "error": "Query vazia"
        }

    normalized_query = query.upper().strip()

    # ------------------------------------------------------
    # BLOQUEAR KEYWORDS PERIGOSAS
    # ------------------------------------------------------

    for keyword in BLOCKED_KEYWORDS:

        pattern = r"\b" + re.escape(keyword) + r"\b"

        if re.search(pattern, normalized_query):

            return {
                "valid": False,
                "error": (
                    f"Operação não permitida: {keyword}"
                )
            }

    # ------------------------------------------------------
    # PERMITIR SOMENTE SELECT/WITH
    # ------------------------------------------------------

    allowed_starts = (
        "SELECT",
        "WITH"
    )

    if not normalized_query.startswith(allowed_starts):

        return {
            "valid": False,
            "error": (
                "Apenas queries SELECT são permitidas"
            )
        }

    return {
        "valid": True,
        "error": None
    }