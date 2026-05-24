"""
InDataLab - Run Script
Inicializa a aplicação Flask
"""

import os
from dotenv import load_dotenv
from app import create_app
from app.database.db import db

# Caminho correto: app.executor.kernel_manager
try:
    from app.executor import kernel_manager
    print("[OK] Kernel Manager carregado de app.executor")
except ImportError as e:
    print(f"[AVISO] kernel_manager não encontrado: {e}")
    kernel_manager = None

load_dotenv('.env')

app = create_app()


@app.shell_context_processor
def make_shell_context():
    from app.models import (
        User, Notebook, Cell, Execution,
        Dataset, AIConversation
    )
    return {
        'db': db,
        'User': User,
        'Notebook': Notebook,
        'Cell': Cell,
        'Execution': Execution,
        'Dataset': Dataset,
        'AIConversation': AIConversation,
    }


if __name__ == '__main__':
    os.makedirs('instance', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    
    port = int(os.getenv('PORT', 5000))
    
    print(f"""
    
    ╔═══════════════════════════════════╗
    ║    InDataLab - ETAPA 3 - MVP      ║
    ║    Backend Consolidado            ║
    ╚═══════════════════════════════════╝
    
    Debug: False
    Database: {app.config.get('SQLALCHEMY_DATABASE_URI')}
    Groq Model: {app.config.get('GROQ_MODEL')}
    
    ▶ Servidor rodando em http://localhost:{port}
    
    """)
    
    app.run(
        debug=False,
        use_reloader=False,
        host='0.0.0.0',
        port=port,
    )