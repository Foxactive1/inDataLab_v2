# Integração Neon — revisão antes de merge

Esta branch usa PostgreSQL/Neon como banco **da aplicação** e preserva arquivos SQLite para células SQL existentes.

## Variáveis de ambiente

```dotenv
FLASK_ENV=development
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
JWT_SECRET_KEY=SUBSTITUA_POR_UM_SEGREDO_FORTE
SECRET_KEY=SUBSTITUA_POR_OUTRO_SEGREDO_FORTE
# Opcional; credencial separada com privilégios APENAS SELECT:
READONLY_DATABASE_URL=postgresql://READONLY_USER:PASSWORD@HOST/DB?sslmode=require
```

Nunca comitar o arquivo .env real. Em produção, configure FLASK_ENV=production, DATABASE_URL, JWT_SECRET_KEY e SECRET_KEY.

## Pré-requisitos e verificação

1. Fazer backup do banco Neon e conferir a branch local efetivamente em execução. Os modelos podem divergir do DDL criado diretamente no Neon.
2. Instalar dependências (`pip install -r requirements.txt`); algumas versões antigas de dependências podem requerer adaptações na instalação com Python 3.14.
3. Executar `python check_neon.py`. Este diagnóstico é **somente leitura**; ele identifica tabelas e colunas, não valida ENUMs, tipos ou constraints.
4. Resolver eventuais incompatibilidades com migrações **revisadas**; não usar `db.create_all()` nem `flask db upgrade` automaticamente contra esquema existente sem primeiro realizar o baseline do Alembic.
5. Executar `python run.py` e abrir `/login`. As rotas `/api/*` exigem JWT, inclusive o Copilot; `/auth/login` e `/auth/register` continuam fora de `/api`.
6. Para células SQL no Neon, configurar uma segunda conexão com uma credencial read-only e usar o alias literal `neon` como `sql_connection`. O driver não deve usar a credencial principal com permissão de escrita.
7. Verificar CRUD de notebooks e células, upload de CSV/XLSX/JSON/DB, execução e Copilot em um banco de staging.

## Limitações conhecidas

- O esquema real do Neon **não foi inspecionado** por esta branch. Não há migrações automáticas nem prova de compatibilidade ORM/DDL.
- O executor Python atual utiliza threads e um namespace em memória, **não é um sandbox seguro**; não disponibilizar execução arbitrária a usuários não confiáveis. `future.cancel()` não interrompe necessariamente código em execução.
- O validador SQL por regex não constitui uma defesa completa. A conta usada em READONLY_DATABASE_URL deve ser efetivamente somente leitura no Postgres.
- Arquivos de datasets e gráficos continuam no disco local; para múltiplas instâncias será necessário armazenamento persistente externo e controle de acesso aos arquivos.
- O HTML/CSS e demais fluxos de autenticação legados podem precisar de revisão antes do deploy. O token atualmente é mantido em localStorage por compatibilidade com a interface existente; avaliar migração para cookie HttpOnly com CSRF.
- Algumas funções legadas, como os caminhos das rotas e serviços menos acessados, ainda exigem testes integrados.

Nenhuma alteração desta branch deve ser interpretada como uma migração efetivamente executada no Neon.
