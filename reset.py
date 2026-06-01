"""
drop_and_recreate.py
"""

from app import create_app
from app.database.db import db

app = create_app()

with app.app_context():

    confirm = input(
        "\nATENÇÃO!\n"
        "Todas as tabelas serão apagadas.\n"
        "Digite RECRIAR para continuar: "
    )

    if confirm != "RECRIAR":
        print("Operação cancelada.")
        exit()

    print("\nRemovendo tabelas...")
    db.drop_all()

    print("Criando tabelas...")
    db.create_all()

    print("\nBanco recriado com sucesso.")