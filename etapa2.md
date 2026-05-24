# InDataLab - ETAPA 2: CRUD Completo Consolidado

## ✅ O que foi implementado

### 🏗️ Arquitetura

```
ETAPA 2 estrutura:

app/
├── services/
│   ├── notebook_service.py   → CRUD notebooks
│   ├── cell_service.py       → CRUD cells + reordenação
│   ├── execution_service.py  → Histórico + stats
│   └── ai_service.py         → [ETAPA 1] Groq
├── routes/
│   ├── notebooks_blueprint.py    → /api/notebooks
│   ├── cells_blueprint.py        → /api/notebooks/{id}/cells
│   ├── executions_blueprint.py   → /api/executions
│   └── __init__.py
├── utils.py                  → APIResponse, ValidateRequest
├── __init__.py               → Registra blueprints
└── [outros]
```

### 🎯 Princípios Aplicados

✅ **Separação de Responsabilidades**
- Services → Lógica de negócio
- Routes → HTTP handling
- Utils → Response/validation padrão

✅ **Modular & Escalável**
- Blueprints separados (routes por recurso)
- Services reutilizáveis
- Error handling centralizado
- Response padrão JSON

✅ **Segurança**
- Autorização (user owns resource)
- Validação entrada
- SQL injection free (SQLAlchemy)

✅ **Sem monólito**
- Zero lógica nas rotas
- Services podem ser testados isolados
- Fácil adicionar features (auth, logging, etc)

---

## 📚 Serviços (Services)

### NotebookService

```python
from app.services.notebook_service import NotebookService

# Criar
notebook, error = NotebookService.create_notebook(
    user_id=1,
    title="Meu Projeto",
    description="...",
    is_public=False
)

# Listar (paginado)
notebooks, total, pages = NotebookService.list_notebooks(
    user_id=1,
    page=1,
    per_page=20
)

# Obter
notebook = NotebookService.get_notebook(notebook_id=1, user_id=1)

# Atualizar
notebook, error = NotebookService.update_notebook(
    notebook_id=1,
    user_id=1,
    title="Novo título",
    is_public=True
)

# Deletar
success, error = NotebookService.delete_notebook(
    notebook_id=1,
    user_id=1
)

# Stats
stats = NotebookService.get_notebook_stats(
    notebook_id=1,
    user_id=1
)
# → {
#     "cell_count": 5,
#     "code_cells": 3,
#     "markdown_cells": 2,
#     "total_executions": 12,
#     ...
#   }
```

### CellService

```python
from app.services.cell_service import CellService

# Criar
cell, error = CellService.create_cell(
    notebook_id=1,
    user_id=1,
    cell_type="code",  # ou "markdown"
    content="print('hello')",
    position=None  # auto-increment
)

# Listar (ordenadas)
cells, error = CellService.list_cells(
    notebook_id=1,
    user_id=1,
    cell_type="code"  # opcional
)

# Obter
cell = CellService.get_cell(cell_id=1, user_id=1)

# Atualizar
cell, error = CellService.update_cell(
    cell_id=1,
    user_id=1,
    content="novo código",
    output="resultado"
)

# Deletar (reordena automaticamente)
success, error = CellService.delete_cell(
    cell_id=1,
    user_id=1
)

# Reordenar (drag-drop)
success, error = CellService.reorder_cells(
    notebook_id=1,
    user_id=1,
    cell_order=[3, 1, 2, 4]
)

# Increment execution count
CellService.increment_execution_count(cell_id=1)
```

### ExecutionService

```python
from app.services.execution_service import ExecutionService

# Criar (quando inicia execução)
execution, error = ExecutionService.create_execution(
    cell_id=1,
    status="running"
)

# Obter
execution = ExecutionService.get_execution(
    execution_id=1,
    user_id=1
)

# Atualizar (após término)
execution, error = ExecutionService.update_execution(
    execution_id=1,
    user_id=1,
    status="success",
    execution_time=2.345,
    logs="output aqui",
    error_message=None
)

# Histórico de uma célula
executions, error = ExecutionService.list_cell_executions(
    cell_id=1,
    user_id=1,
    page=1,
    limit=50
)

# Todas as execuções do notebook
executions, total, pages, error = ExecutionService.list_notebook_executions(
    notebook_id=1,
    user_id=1,
    page=1,
    limit=100
)

# Stats (taxa sucesso, tempo médio, etc)
stats = ExecutionService.get_execution_stats(
    cell_id=1,
    user_id=1
)
# → {
#     "total_executions": 10,
#     "successful": 9,
#     "errors": 1,
#     "success_rate": 90.0,
#     "avg_execution_time": 2.1,
#     ...
#   }
```

---

## 🔌 Rotas da API

### Base URL
```
http://localhost:5000/api
```

### Notebooks

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/notebooks` | Criar notebook |
| GET | `/notebooks` | Listar (paginado) |
| GET | `/notebooks/{id}` | Obter + stats |
| PUT | `/notebooks/{id}` | Atualizar |
| DELETE | `/notebooks/{id}` | Deletar |

### Cells

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/notebooks/{id}/cells` | Criar célula |
| GET | `/notebooks/{id}/cells` | Listar (ordenadas) |
| GET | `/notebooks/{id}/cells/{id}` | Obter célula |
| PUT | `/notebooks/{id}/cells/{id}` | Atualizar |
| DELETE | `/notebooks/{id}/cells/{id}` | Deletar |
| POST | `/notebooks/{id}/cells/reorder` | Reordenar |

### Executions

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/notebooks/{id}/cells/{id}/execute` | Iniciar execução |
| PUT | `/notebooks/{id}/executions/{id}` | Atualizar com resultado |
| GET | `/notebooks/{id}/cells/{id}/executions` | Histórico célula |
| GET | `/notebooks/{id}/executions` | Todas execuções |
| GET | `/notebooks/{id}/cells/{id}/stats` | Stats execução |

---

## 🎯 Resposta Padrão

Todas as rotas retornam JSON padronizado:

### ✅ Sucesso (2xx)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "title": "...",
    ...
  },
  "message": "Notebook criado com sucesso"
}
```

### ❌ Erro (4xx/5xx)
```json
{
  "success": false,
  "error": "Título é obrigatório",
  "status_code": 400,
  "validation_errors": {
    "title": "Título é obrigatório"
  }
}
```

---

## 🔐 Autorização

Todos os endpoints validam autorização:

```python
# Exemplo: notebook deve pertencer ao user
if notebook.user_id != user_id:
    return None, "Sem permissão"
```

**Atualmente hardcoded `user_id=1` para MVP.**

Antes de ETAPA 3, implementar:
- JWT auth
- Middleware de autenticação
- Roles/permissões

---

## ✅ Validações Implementadas

### NotebookService
- ✅ Título obrigatório
- ✅ Título 1-255 caracteres
- ✅ Autorização (user owns)
- ✅ Soft-delete ready (is_archived)

### CellService
- ✅ cell_type validado (code | markdown)
- ✅ Conteúdo obrigatório
- ✅ Position auto-incrementada
- ✅ Reordenação automática ao deletar
- ✅ Autorização validada

### ExecutionService
- ✅ Status validado
- ✅ Incremento execution_count automático
- ✅ Paginação
- ✅ Stats accuracy

---

## 🧪 Fluxo de Teste (Quick Start)

```bash
# Terminal 1: Servidor
python run.py

# Terminal 2: Teste
# 1. Criar notebook
curl -X POST http://localhost:5000/api/notebooks \
  -H "Content-Type: application/json" \
  -d '{"title":"Teste"}'

# 2. Criar célula (substitua {id})
curl -X POST http://localhost:5000/api/notebooks/1/cells \
  -H "Content-Type: application/json" \
  -d '{"cell_type":"code","content":"print(1+1)"}'

# 3. Executar
curl -X POST http://localhost:5000/api/notebooks/1/cells/1/execute \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}'

# 4. Finalizar execução
curl -X PUT http://localhost:5000/api/notebooks/1/executions/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"success","execution_time":0.1,"logs":"2"}'

# 5. Ver stats
curl http://localhost:5000/api/notebooks/1/cells/1/stats
```

---

## 📊 Padrão de Erro Centralizado

Via `app/utils.py`:

```python
# Sucesso
resp, code = APIResponse.success(
    data={...},
    message="ok",
    status_code=201
)

# Erros padrão
APIResponse.not_found("Recurso")      # 404
APIResponse.bad_request("msg")        # 400
APIResponse.unauthorized()            # 401
APIResponse.forbidden()               # 403
APIResponse.internal_error("msg")     # 500

# Validação
ValidateRequest.required_fields(data, ['field1', 'field2'])
ValidateRequest.field_type(data, 'field', str, allow_none=True)
ValidateRequest.field_length(data, 'field', min_length=1, max_length=255)
```

---

## 🔄 Workflow Típico (Notebook User)

```
1. User cria notebook
   POST /api/notebooks → {notebook_id: 1}

2. User cria células
   POST /api/notebooks/1/cells → {cell_id: 1}
   POST /api/notebooks/1/cells → {cell_id: 2}
   POST /api/notebooks/1/cells → {cell_id: 3}

3. User edita célula
   PUT /api/notebooks/1/cells/2

4. User reordena células
   POST /api/notebooks/1/cells/reorder

5. User executa célula
   POST /api/notebooks/1/cells/1/execute → {execution_id: 1}

6. Backend executa (ETAPA 3)
   [Python executor aqui]

7. Backend retorna resultado
   PUT /api/notebooks/1/executions/1
   {status: success, execution_time: 2.3, logs: ...}

8. User vê stats
   GET /api/notebooks/1/cells/1/stats
```

---

## 🚀 Próxima Etapa: ETAPA 3

### Notebook Engine

Será implementado:
- [ ] Python executor isolado (subprocess)
- [ ] DuckDB integração (SQL cells)
- [ ] Output streaming (WebSocket)
- [ ] Kernel management
- [ ] Timeout handling
- [ ] Memory limits
- [ ] Error capture detalhado

### Autenticação

Antes de ir para prod:
- [ ] JWT implementation
- [ ] Login/register routes
- [ ] Refresh tokens
- [ ] User context middleware

---

## 📁 Estrutura de Diretórios (Completa)

```
indatalab/
├── app/
│   ├── __init__.py              ← Factories + blueprints
│   ├── config.py                ← Configs (dev/prod)
│   ├── utils.py                 ← APIResponse, ValidateRequest
│   ├── database/
│   │   ├── __init__.py
│   │   └── db.py                ← SQLAlchemy + Migrate
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── notebook.py
│   │   ├── cell.py
│   │   ├── execution.py
│   │   ├── dataset.py
│   │   └── ai_conversation.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── notebook_service.py  ← CRUD notebooks
│   │   ├── cell_service.py      ← CRUD cells
│   │   ├── execution_service.py ← Execução + stats
│   │   └── ai_service.py        ← Groq integração
│   └── routes/
│       ├── __init__.py
│       ├── notebooks_blueprint.py
│       ├── cells_blueprint.py
│       └── executions_blueprint.py
├── instance/                    ← .gitignored
│   └── indatalab.db            ← SQLite
├── uploads/                     ← .gitignored
├── migrations/                  ← Flask-Migrate
├── .env                         ← Variáveis (GROQ_API_KEY, etc)
├── .env.example                 ← Template
├── .gitignore
├── requirements.txt
├── run.py                       ← Entry point
├── README.md                    ← Setup
├── MODELS.md                    ← Documentação models
├── API_TEST.md                  ← Testes de API
└── ETAPA_2.md                   ← Este arquivo
```

---

## ⚠️ Importante: Hardcoded `user_id=1`

Atualmente, todos os endpoints assumem `user_id=1` (mock).

Para autenticar corretamente em ETAPA 3/produção:

```python
# Hoje (ETAPA 2)
user_id = 1

# Depois (ETAPA 3+)
from flask_jwt_extended import get_jwt_identity
user_id = get_jwt_identity()
```

---

## 🎓 Aprendizados aplicados

1. **Service Pattern** → Lógica de negócio isolada
2. **Blueprint Pattern** → Rotas modulares
3. **Factory Pattern** → Criação de app
4. **Validation Pattern** → Centralizado em utils
5. **Response Pattern** → JSON padrão
6. **Authorization Pattern** → User owns resource

---

**Dione Castro Alves | InNovaIdeia | 2025**

Status: ✅ **ETAPA 2 - COMPLETA**
Next: ⏳ **ETAPA 3 - Notebook Engine + Python Executor**
