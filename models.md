# InDataLab - Documentação de Models

## User

**Tabela**: `users`

Representa usuários da plataforma.

### Campos

| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| id | Integer | PK | ID único |
| name | String(120) | NOT NULL | Nome do usuário |
| email | String(120) | UNIQUE, NOT NULL, INDEX | Email único |
| password_hash | Text | NOT NULL | Hash bcrypt/argon2 |
| is_active | Boolean | DEFAULT True | Ativo/inativo |
| created_at | DateTime | DEFAULT now | Criação |
| updated_at | DateTime | DEFAULT now, UPDATE | Atualização |

### Relacionamentos

- **notebooks** (1:N) → Notebook
- **ai_conversations** (1:N) → AIConversation

---

## Notebook

**Tabela**: `notebooks`

Representa notebooks (projetos) dos usuários.

### Campos

| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| id | Integer | PK | ID único |
| user_id | Integer | FK users, INDEX | Proprietário |
| title | String(255) | NOT NULL | Título |
| description | Text | - | Descrição |
| is_public | Boolean | DEFAULT False, INDEX | Público? |
| is_archived | Boolean | DEFAULT False | Arquivado? |
| kernel_type | String(50) | DEFAULT python3 | Tipo de kernel |
| created_at | DateTime | DEFAULT now | Criação |
| updated_at | DateTime | DEFAULT now, UPDATE | Atualização |

### Relacionamentos

- **user** (N:1) ← User
- **cells** (1:N) → Cell
- **datasets** (1:N) → Dataset

---

## Cell

**Tabela**: `cells` — O CORAÇÃO DO SISTEMA

Representa células dentro de um notebook (código ou markdown).

### Campos

| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| id | Integer | PK | ID único |
| notebook_id | Integer | FK notebooks, INDEX | Notebook |
| cell_type | String(50) | NOT NULL, DEFAULT code | code ou markdown |
| content | Text | NOT NULL | Código Python ou markdown |
| output | Text | - | Resultado da execução |
| position | Integer | DEFAULT 0 | Ordem |
| execution_count | Integer | DEFAULT 0 | Quantas vezes executou |
| is_hidden | Boolean | DEFAULT False | Oculta? |
| tags | Text | - | Tags (csv) |
| created_at | DateTime | DEFAULT now | Criação |
| updated_at | DateTime | DEFAULT now, UPDATE | Atualização |

### Relacionamentos

- **notebook** (N:1) ← Notebook
- **executions** (1:N) → Execution

### Notas

- `output` armazena STDOUT, JSON, HTML (até 1GB em SQLite)
- `execution_count` rastreia quantas vezes rodou
- `position` define ordem de exibição

---

## Execution

**Tabela**: `executions`

Histórico de cada execução de célula.

### Campos

| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| id | Integer | PK | ID único |
| cell_id | Integer | FK cells, INDEX | Célula |
| status | String(20) | INDEX, DEFAULT pending | pending/running/success/error |
| execution_time | Float | - | Tempo em segundos |
| logs | Text | - | Stdout |
| error_message | Text | - | Mensagem de erro |
| stderr | Text | - | Stderr |
| memory_used | Float | - | Memória em MB |
| executed_at | DateTime | INDEX, DEFAULT now | Quando executou |
| created_at | DateTime | DEFAULT now | Registro |

### Status Workflow

```
pending → running → success
              ↓
            error
```

---

## Dataset

**Tabela**: `datasets`

Arquivos e dados associados ao notebook.

### Campos

| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| id | Integer | PK | ID único |
| notebook_id | Integer | FK notebooks, INDEX | Notebook |
| filename | String(255) | NOT NULL | Nome original |
| file_type | String(20) | NOT NULL | csv/json/xlsx/parquet |
| file_path | Text | NOT NULL | uploads/... |
| file_size | BigInteger | - | Bytes |
| rows | Integer | - | Linhas (tabulado) |
| columns | Integer | - | Colunas (tabulado) |
| column_names | Text | - | JSON array |
| description | Text | - | Descrição |
| is_public | Boolean | DEFAULT False | Compartilhável |
| metadata | Text | - | JSON adicional |
| created_at | DateTime | DEFAULT now | Upload |
| updated_at | DateTime | DEFAULT now, UPDATE | Atualização |

### Tipos Suportados

- CSV (.csv)
- JSON (.json)
- Excel (.xlsx, .xls)
- Parquet (.parquet)
- Texto (.txt)

---

## AIConversation

**Tabela**: `ai_conversations`

Histórico de conversas com Groq API.

### Campos

| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| id | Integer | PK | ID único |
| user_id | Integer | FK users, INDEX | Usuário |
| notebook_id | Integer | FK notebooks | Notebook (contexto) |
| cell_id | Integer | FK cells | Célula (contexto) |
| conversation_session_id | String(100) | INDEX | ID da sessão |
| role | String(20) | NOT NULL, INDEX, DEFAULT user | user/assistant |
| content | Text | NOT NULL | Mensagem |
| model | String(100) | DEFAULT llama-3.3... | Modelo usado |
| temperature | Float | DEFAULT 0.7 | Temperature |
| tokens_used | Integer | - | Total tokens |
| input_tokens | Integer | - | Prompt tokens |
| output_tokens | Integer | - | Completion tokens |
| processing_time | Float | - | Tempo em ms |
| groq_request_id | String(100) | - | ID da requisição Groq |
| metadata | Text | - | JSON (system_prompt, etc) |
| created_at | DateTime | INDEX, DEFAULT now | Criação |

### Uso

```python
from app.services.ai_service import AIService

# Dentro de app context
ai = AIService()
result = ai.chat_completion(
    user_id=1,
    content="Sua pergunta",
    notebook_id=1,  # opcional
    conversation_session_id="sess_abc123"  # agrupa conversa
)
```

---

## Relacionamentos Visuais

```
User
  ├─ Notebook (1:N)
  │   ├─ Cell (1:N)
  │   │   └─ Execution (1:N)
  │   └─ Dataset (1:N)
  └─ AIConversation (1:N)
```

---

## Índices (Performance)

Já definidos para otimizar queries comuns:

- `users.email` (UNIQUE)
- `notebooks.user_id`
- `notebooks.is_public`
- `cells.notebook_id`
- `datasets.notebook_id`
- `executions.cell_id`
- `executions.status`
- `ai_conversations.user_id`
- `ai_conversations.conversation_session_id`

---

## Constraints & Cascades

Todos os relacionamentos com `cascade='all, delete-orphan'`:
- Deletar Notebook → deleta seus Cells
- Deletar Cell → deleta suas Executions
- Deletar User → deleta tudo associado

---

## Serialização

Todos os models implementam `.to_dict()`:

```python
notebook = Notebook.query.get(1)
json_data = notebook.to_dict()
# {
#     'id': 1,
#     'user_id': 1,
#     'title': '...',
#     ...
# }
```

---

## Próximas Features (Pronta a integrar)

- [ ] Soft deletes (is_deleted flag)
- [ ] Versioning para Cells
- [ ] Comments em Cells
- [ ] Sharing/Permissions
- [ ] Webhooks
- [ ] API Keys para usuários

---

**Gerado: ETAPA 1 - Fundação Consolidada**
