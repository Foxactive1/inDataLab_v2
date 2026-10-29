# Deploy do InDataLab — Vercel + Render

Esta configuração separa o frontend estático (Vercel) da API Flask (Render). O PostgreSQL deve ficar no Neon.

## 1. Preparar o Neon

1. Crie/seleciona o projeto PostgreSQL no Neon.
2. Copie a connection string PostgreSQL com SSL. Prefira a connection string pooled quando disponível.
3. Não publique essa URL no GitHub. Ela será cadastrada como `DATABASE_URL` no Render.
4. Antes do primeiro acesso, confirme que o schema/tabelas existentes no Neon correspondem aos modelos em `app/models`. Este repositório ainda não contém uma pasta `migrations/` versionada; portanto, não presuma que `flask db upgrade` esteja pronto para criar o schema.

## 2. Backend no Render

1. No Render, escolha **New → Blueprint** e conecte este repositório, ou crie um **Web Service** manualmente.
2. Para Web Service manual: Root Directory `.`, Runtime Python, Build Command `pip install -r requirements.txt`, Start Command `gunicorn run:app --workers 1 --threads 4 --timeout 120`.
3. Configure Health Check Path como `/health`.
4. Configure as variáveis:

| Variável | Valor |
|---|---|
| `FLASK_ENV` | `production` |
| `DATABASE_URL` | URL PostgreSQL do Neon, com SSL |
| `SECRET_KEY` | segredo forte e aleatório |
| `JWT_SECRET_KEY` | outro segredo forte e aleatório |
| `CORS_ORIGINS` | origens Vercel separadas por vírgula |
| `GROQ_API_KEY` | chave da Groq (opcional se IA não for usada) |
| `ENABLE_KERNELS` | `false` |

Exemplo de `CORS_ORIGINS`: `https://SEU-PROJETO.vercel.app,https://seudominio.com.br`. Informe somente as origens reais, sem barra no final. Inclua domínio de produção e domínio customizado, se houver.

O arquivo `render.yaml` já descreve o serviço e gera os dois segredos automaticamente. A URL do banco e as origens CORS precisam ser informadas manualmente.

Depois do deploy, teste `https://SUA-API.onrender.com/health`. Deve retornar JSON com `status: healthy`.

## 3. Frontend no Vercel

1. Importe o mesmo repositório no Vercel.
2. Defina **Root Directory** como `frontend`.
3. Framework Preset: **Other**. Não é necessário comando de build; o frontend é HTML/CSS/JavaScript estático.
4. Em `frontend/assets/js/config.js`, substitua `https://YOUR-INDATALAB-BACKEND.onrender.com` pela URL real do serviço Render, sem barra final.
5. Faça commit dessa URL pública da API e aguarde o novo deploy do Vercel.
6. Copie o domínio final `.vercel.app` e adicione-o a `CORS_ORIGINS` no Render. Se usar domínio próprio, inclua-o também.

O frontend usa `index.html` como entrada e `login.html` para autenticação. Não coloque segredos de banco, JWT ou Groq no frontend.

## 4. Limitações conhecidas antes de abrir ao público

- **Execução Python:** está bloqueada por padrão em produção (resposta HTTP 503). O executor atual não é um sandbox de segurança. Não defina `ENABLE_KERNELS=true` em um serviço público até implementar isolamento real por processo/container, limites de CPU/memória/tempo, filesystem restrito e política de rede.
- **Uploads:** o diretório local do Render é efêmero por padrão. Arquivos enviados podem desaparecer em reinicializações ou novos deploys. Para persistência, configure um Persistent Disk pago e defina `UPLOAD_FOLDER=/var/data/uploads`, ou implemente object storage (S3/R2). O banco guarda metadados; não substitui o armazenamento dos arquivos.
- **Neon:** valide o schema e os relacionamentos antes de usar dados reais. Não execute migrações não revisadas diretamente em produção.
- **Autenticação:** os endpoints de login/registro ficam em `/auth/login` e `/auth/register`; APIs protegidas ficam em `/api/*` e recebem JWT no header `Authorization: Bearer ...`.
- **CORS:** cada origem deve ser cadastrada exatamente em `CORS_ORIGINS`. Ao alterar domínio, atualize a variável no Render.

## 5. Testes de homologação

- [ ] `GET /health` responde 200.
- [ ] Registro e login funcionam a partir do domínio Vercel.
- [ ] Login retorna `access_token`.
- [ ] Chamadas autenticadas a `/api/notebooks` funcionam.
- [ ] Chamadas sem JWT a `/api/*` são rejeitadas.
- [ ] CORS permite o domínio Vercel e bloqueia origens não autorizadas.
- [ ] CRUD de notebooks/células e Copilot são validados.
- [ ] Upload e persistência são validados após configurar armazenamento persistente.
- [ ] Execução Python retorna 503 enquanto não existir sandbox.

Este guia prepara a estrutura de deploy; não substitui a execução dos testes nem a configuração das contas Render, Vercel e Neon.
