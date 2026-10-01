"""Diagnóstico somente leitura: divergências entre modelos ORM e esquema Neon.

Executar: python check_neon.py
Não cria tabelas e não executa migrações.
"""
from sqlalchemy import inspect, text

from app import create_app
from app.database.db import db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    existing = set(inspector.get_table_names())
    mapped = set(db.metadata.tables)

    with db.engine.connect() as conn:
        name, schema = conn.execute(
            text("SELECT current_database(), current_schema()")
        ).one()
    print(f"Database: {name}; schema: {schema}")

    for table in sorted(mapped - existing):
        print(f"TABLE MISSING: {table}")
    for table in sorted(mapped & existing):
        columns = {column["name"] for column in inspector.get_columns(table)}
        expected = set(db.metadata.tables[table].columns)
        for column in sorted(expected - columns):
            print(f"COLUMN MISSING: {table}.{column}")
        for column in sorted(columns - expected):
            print(f"EXTRA COLUMN: {table}.{column}")
    print("Diagnóstico somente leitura finalizado. Tipos, constraints e ENUMs exigem revisão adicional.")
