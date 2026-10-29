# InDataLab Frontend (Vercel)

Este diretório contém a versão estática da interface. Configure o projeto Vercel com **Root Directory = frontend** e Framework Preset **Other**.

Antes do deploy, edite `assets/js/config.js` e informe a URL pública do backend Flask no Render em `API_URL`. A URL deve ser HTTPS e não deve terminar com barra.

O frontend utiliza HTML, CSS e JavaScript sem etapa de build. Consulte `../DEPLOYMENT.md` para configurar Render, CORS e Neon.
