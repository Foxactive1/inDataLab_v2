# InDataLab - ETAPA 1: Fundação Backend Consolidada

## 📋 Visão Geral

Fundação backend modular, escalável e pronta para crescimento.

- **Framework**: Flask 3.0
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Flask-Migrate
- **Database**: SQLite (MVP) / PostgreSQL (produção)
- **IA**: Groq API (llama-3.3-70b-versatile)
- **Data**: Pandas + DuckDB

## 🏗️ Arquitetura

```
indatalab/
├── app/
│   ├── __init__.py          # Factory de aplicação
│   ├── config.py            # Configurações
│   ├── database/
│   │   └── db.py            # SQLAlchemy + Migrate
│   ├── models/
│   │   ├── user.py          # Usuários
│   │   ├── notebook.py      # Notebooks (projetos)
│   │   ├── cell.py          # Células (código/markdown)
│   │   ├── execution.py     # Histórico de execuções
│   │   ├── dataset.py       # Arquivos/datasets
│   │   └── ai_conversation.py # Histórico Groq
│   ├── services/
│   │   └── ai_service.py    # Integração Groq
│   └── routes/              # (ETAPA 2)
├── instance/                # Arquivos de instância (gitignored)
├── uploads/                 # Uploads de usuários
├── .env                     # Variáveis de ambiente
├── .env.example             # Template de .env
├── requirements.txt         # Dependências Python
└── run.py                   # Script de inicialização
```

## 🚀 Instalação e Setup (Linux/Termux)

### 1️⃣ Clonar ou criar o projeto

```bash
cd /caminho/para/projeto
git clone <repo> indatalab
cd indatalab
```

### 2️⃣ Criar ambiente virtual

```bash
# Python 3.9+
python3 -m venv venv

# Ativar
source venv/bin/activate  # Linux/Mac
# ou
source venv/Scripts/activate  # Windows
```

### 3️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

### 4️⃣ Configurar .env

```bash
# Copiar template
cp .env.example .env

# Editar .env com sua chave Groq
# Abrir com seu editor favorito:
# nano .env
# vim .env
# code .env (VS Code)
```

**Importante**: Adicione sua chave Groq em `GROQ_API_KEY`:
- Obtém em: https://console.groq.com/keys

### 5️⃣ Inicializar banco de dados

```bash
# Define variável de ambiente
export FLASK_APP=run.py

# Cria pasta de migrations
flask db init

# Cria primeira migration
flask db migrate -m "Initial migration"

# Aplica migration (cria tabelas)
flask db upgrade

# Verificar banco (optional)
# sqlite3 instance/indatalab.db ".tables"
```

### 6️⃣ Rodar aplicação

```bash
python run.py
```

Esperado:
```
╔═══════════════════════════════════╗
║    InDataLab - ETAPA 1 - MVP      ║
║    Backend Consolidado            ║
╚═══════════════════════════════════╝

Flask: True
Database: sqlite:///instance/indatalab.db
Groq Model: llama-3.3-70b-versatile

▶ Servidor rodando em http://localhost:5000
```

## 📝 Uso Prático (Python/Flask Shell)

```bash
# Entrar no shell Flask
flask shell

# Criar usuário
>>> from app.models import User, Notebook, Cell
>>> from app.database.db import db

>>> user = User(
...     name="Dione",
...     email="dione@indatalab.com",
...     password_hash="hash_aqui"
... )
>>> db.session.add(user)
>>> db.session.commit()

# Criar notebook
>>> notebook = Notebook(
...     user_id=user.id,
...     title="Análise de Dados",
...     description="Meu primeiro notebook"
... )
>>> db.session.add(notebook)
>>> db.session.commit()

# Criar célula
>>> cell = Cell(
...     notebook_id=notebook.id,
...     cell_type="code",
...     content="import pandas as pd\npd.read_csv('data.csv')",
...     position=0
... )
>>> db.session.add(cell)
>>> db.session.commit()

# Sair
>>> exit()
```

## 🤖 Testar Groq API (Python)

```python
from app import create_app
from app.services.ai_service import AIService

app = create_app()

with app.app_context():
    ai = AIService()
    
    result = ai.chat_completion(
        user_id=1,
        content="Explique machine learning em 2 frases",
        model="llama-3.3-70b-versatile"
    )
    
    print(result)
```

## 📊 Models - Relacionamentos

```
User (1) ──┬──→ (∞) Notebook
           └──→ (∞) AIConversation

Notebook ─→ (∞) Cell
         ─→ (∞) Dataset

Cell ────→ (∞) Execution

AIConversation
  - references User
  - optional: references Notebook, Cell
```

## 🔌 Próximas Etapas

### ETAPA 2: CRUD Completo
- Routes para Notebooks (GET, POST, PUT, DELETE)
- Routes para Cells (execução, CRUD)
- Services para orquestração
- Templates base (ou JSON API)

### ETAPA 3: Notebook Engine
- Executor Python seguro
- Kernel management
- Output streaming

### ETAPA 4: Python Executor + DuckDB
- DuckDB integrado para queries SQL
- Cache de resultados
- Performance optimization

## ✅ Checklist de Validação

- [ ] Banco de dados criado (`instance/indatalab.db` existe)
- [ ] Migrations aplicadas (0 errors ao `flask db upgrade`)
- [ ] Groq API key configurada em `.env`
- [ ] App inicia sem erros (`python run.py`)
- [ ] Flask shell funciona (`flask shell`)
- [ ] Modelos importam corretamente
- [ ] IA service responde à chamada

## 🐛 Troubleshooting

### "Groq API key não configurada"
```bash
# Verificar .env
cat .env | grep GROQ_API_KEY

# Deve estar preenchida:
GROQ_API_KEY=gsk_xxx...
```

### "ModuleNotFoundError: No module named 'groq'"
```bash
pip install groq --upgrade
```

### "Database locked"
```bash
# Remove banco e refaz
rm instance/indatalab.db
flask db upgrade
```

### Migrations conflitantes
```bash
# Reset completo (⚠️ deleta dados)
rm -rf migrations/
rm instance/indatalab.db
flask db init
flask db migrate -m "Initial"
flask db upgrade
```

## 📚 Recursos

- Documentação Flask: https://flask.palletsprojects.com/
- SQLAlchemy ORM: https://docs.sqlalchemy.org/
- Groq API: https://console.groq.com/docs/
- Flask-Migrate: https://flask-migrate.readthedocs.io/

---

**Dione Castro Alves | InNovaIdeia | 2025**
