// cell.js - Versão completa com snippets e execução plena
class CellManager {
    constructor() {
        this.currentExecutingId = null;
        this._setupDelegation();
        this._setupExecutionModal();
        this._setupModalCleanup();   // remove listener dos snippets ao fechar modal
    }

    // ============================================================
    // DELEGAÇÃO DE EVENTOS
    // ============================================================
    _setupDelegation() {
        const container = document.getElementById('cellsContainer');
        if (!container) return;

        container.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;

            const action = btn.dataset.action;
            const id     = Number(btn.dataset.id);

            switch (action) {
                case 'move-up':   this.moveCell(id, 'up');   break;
                case 'move-down': this.moveCell(id, 'down'); break;
                case 'edit':      this.editCell(id);         break;
                case 'execute':   this.executeCell(id);      break;
                case 'delete':    this.deleteCell(id);       break;
            }
        });
    }

    // ============================================================
    // MODAL DE EXECUÇÃO
    // ============================================================
    _setupExecutionModal() {
        const runBtn = document.getElementById('runCellBtn');
        if (!runBtn) return;

        runBtn.addEventListener('click', () => {
            if (this.currentExecutingId !== null) return;
            const id = Number(runBtn.dataset.cellId);
            if (id) this.executeCell(id);
        });
    }

    // ============================================================
    // LIMPEZA DO MODAL DE EDIÇÃO (para snippets)
    // ============================================================
    _setupModalCleanup() {
        const modalEl = document.getElementById('cellModal');
        if (!modalEl) return;
        modalEl.addEventListener('hidden.bs.modal', () => {
            this._removeSnippetsListener();
        });
    }

    // ============================================================
    // CARREGAR CÉLULAS
    // ============================================================
    async loadCells() {
        const nbId = app.notebook.currentId;
        if (!nbId) return;

        this._setContainerLoading(true);

        try {
            const data = await API.get(`/notebooks/${nbId}/cells`);
            if (data.success) {
                this.renderCells(data.data.cells);
            } else {
                app.toast('Não foi possível carregar as células.', 'warning');
            }
        } catch (err) {
            app.toast('Erro ao carregar células: ' + err.message, 'danger');
        } finally {
            this._setContainerLoading(false);
        }
    }

    // ============================================================
    // RENDERIZAR CÉLULAS (com suporte total a Markdown, highlight, mermaid, math)
    // ============================================================
    renderCells(cells) {
    const container = document.getElementById('cellsContainer');

    if (!cells || cells.length === 0) {
        container.innerHTML = `
            <div class="text-muted p-5 text-center">
                <i class="bi bi-plus-circle fs-2 d-block mb-2"></i>
                Clique em <strong>Célula</strong> para adicionar
            </div>`;
        return;
    }

    const total    = cells.length;
    const fragment = document.createDocumentFragment();

    cells.forEach((cell, idx) => {
        const card = document.createElement('div');
        card.className      = `cell-card ${cell.cell_type}`;
        card.dataset.cellId = cell.id;
        card.tabIndex       = 0;

        const header = document.createElement('div');
        header.className = 'cell-header';

        const meta = document.createElement('div');
        meta.className = 'd-flex gap-2 align-items-center';
        meta.innerHTML = `
            <span class="badge-cell">${escapeHtml(cell.cell_type.toUpperCase())}</span>
            <small class="text-muted">#${cell.position}</small>`;

        const actions = document.createElement('div');
        actions.className = 'd-flex gap-1';
        actions.appendChild(this._btn('move-up',   cell.id, 'bi-arrow-up',   'Mover para cima',  idx === 0));
        actions.appendChild(this._btn('move-down', cell.id, 'bi-arrow-down', 'Mover para baixo', idx === total - 1));
        actions.appendChild(this._btn('edit',      cell.id, 'bi-pencil',     'Editar'));
        
        // --- Alteração: desabilitar execução para markdown ---
        const isExecutable = ['python', 'sql', 'groq'].includes(cell.cell_type);
        actions.appendChild(this._btn('execute', cell.id, 'bi-play-fill', 'Executar', !isExecutable));
        
        actions.appendChild(this._btn('delete',    cell.id, 'bi-trash',      'Excluir', false, true));

        header.appendChild(meta);
        header.appendChild(actions);

        const body = document.createElement('div');
        body.className = `cell-code${cell.cell_type === 'markdown' ? ' cell-markdown' : ''}`;

        if (cell.cell_type === 'markdown') {
            body.innerHTML = marked.parse(cell.content || '');
            body.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
            if (window.renderMathInElement) {
                renderMathInElement(body);
            }
            if (window.mermaid) {
                mermaid.run({
                    nodes: body.querySelectorAll('.language-mermaid')
                });
            }
        } else {
            const pre = document.createElement('pre');
            pre.textContent = cell.content || '';
            body.appendChild(pre);
        }

        card.appendChild(header);
        card.appendChild(body);

        const output = cell.output || cell.html || cell.result;
        if (output) {
            const outputEl = document.createElement('div');
            outputEl.className = 'cell-output';
            this._renderOutput(outputEl, output);
            card.appendChild(outputEl);
        }

        fragment.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(fragment);
}

    // ============================================================
    // EXECUTAR CÉLULA (Python/SQL)
    // ============================================================
    async executeCell(id) {
        if (this.currentExecutingId !== null) {
            app.toast('Aguarde a execução atual terminar.', 'warning');
            return;
        }

        this.currentExecutingId = id;

        const modalEl = document.getElementById('executionModal');
        const modal   = bootstrap.Modal.getOrCreateInstance(modalEl);
        const logDiv  = document.getElementById('execLogs');
        const runBtn  = document.getElementById('runCellBtn');

        logDiv.innerHTML = `
            <div class="progress">
                <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary"
                     style="width: 100%" role="progressbar"></div>
            </div>
            <small class="text-muted d-block mt-2">Executando célula #${id}…</small>`;

        runBtn.disabled        = true;
        runBtn.dataset.cellId  = id;

        modal.show();

        try {
            const data = await API.post(`/executions/cells/${id}/execute`, {});

            if (data.success) {
                this._renderOutputModal(data);
                await this.loadCells();
                app.toast('Célula executada com sucesso.', 'success');
            } else {
                this._showModalError(data.error || 'Erro desconhecido');
            }
        } catch (err) {
            this._showModalError(err.message);
        } finally {
            this.currentExecutingId = null;
            runBtn.disabled = false;
        }
    }

    // ============================================================
    // MOVER CÉLULA
    // ============================================================
    async moveCell(id, direction) {
        try {
            const data = await API.post(
                `/notebooks/${app.notebook.currentId}/cells/${id}/move?direction=${direction}`,
                {}
            );
            if (data.success) {
                await this.loadCells();
            } else {
                app.toast('Não foi possível mover a célula.', 'warning');
            }
        } catch (err) {
            app.toast('Erro ao mover célula: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // EXCLUIR CÉLULA
    // ============================================================
    async deleteCell(id) {
        const confirmed = await this._confirm('Remover célula?', 'Esta ação não pode ser desfeita.');
        if (!confirmed) return;

        try {
            const data = await API.delete(`/notebooks/${app.notebook.currentId}/cells/${id}`);
            if (data.success) {
                await this.loadCells();
                app.toast('Célula removida.', 'info');
            } else {
                app.toast('Erro ao excluir: ' + (data.error || 'Erro desconhecido'), 'danger');
            }
        } catch (err) {
            app.toast('Erro ao excluir célula: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // MODAL — NOVA CÉLULA
    // ============================================================
    openNewModal() {
        this._fillCellModal(null);
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('cellModal')
        ).show();
    }

    // ============================================================
    // MODAL — EDITAR CÉLULA
    // ============================================================
    async editCell(id) {
        try {
            const data = await API.get(`/notebooks/${app.notebook.currentId}/cells/${id}`);
            if (data.success) {
                this._fillCellModal(data.data);
                bootstrap.Modal.getOrCreateInstance(
                    document.getElementById('cellModal')
                ).show();
            } else {
                app.toast('Não foi possível carregar a célula.', 'warning');
            }
        } catch (err) {
            app.toast('Erro ao carregar célula: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // SALVAR CÉLULA
    // ============================================================
    async save() {
        const id      = document.getElementById('cellId').value;
        let cellType  = document.getElementById('cellType').value;
        const content = document.getElementById('cellContent').value.trim();

        if (!content) {
            document.getElementById('cellContent').focus();
            app.toast('O conteúdo da célula não pode estar vazio.', 'warning');
            return;
        }

        if (cellType === 'code') cellType = 'python'; // compatibilidade legada

        const payload = {
            cell_type:      cellType,
            content,
            sql_connection: cellType === 'sql'
                ? document.getElementById('cellSqlConnection').value.trim()
                : null,
        };

        const saveBtn = document.querySelector('#cellModal .btn-primary');
        if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Salvando…'; }

        try {
            const method = id ? 'put' : 'post';
            const url    = id
                ? `/notebooks/${app.notebook.currentId}/cells/${id}`
                : `/notebooks/${app.notebook.currentId}/cells`;

            const data = await API[method](url, payload);

            if (data.success) {
                bootstrap.Modal.getInstance(
                    document.getElementById('cellModal')
                )?.hide();
                await this.loadCells();
                app.toast('Célula salva.', 'success');
            } else {
                app.toast('Erro: ' + (data.error || 'Erro desconhecido'), 'danger');
            }
        } catch (err) {
            app.toast('Falha ao salvar célula: ' + err.message, 'danger');
        } finally {
            if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Salvar'; }
        }
    }

    // ============================================================
    // HELPERS PRIVADOS
    // ============================================================

    _btn(action, id, icon, title, disabled = false, danger = false) {
        const btn = document.createElement('button');
        btn.className        = `btn-icon-sm${danger ? ' text-danger' : ''}`;
        btn.title            = title;
        btn.disabled         = disabled;
        btn.dataset.action   = action;
        btn.dataset.id       = id;
        btn.innerHTML        = `<i class="bi ${icon}"></i>`;
        return btn;
    }

    _fillCellModal(cell) {
        document.getElementById('cellId').value              = cell?.id          ?? '';
        document.getElementById('cellContent').value         = cell?.content     ?? '';
        document.getElementById('cellType').value            = cell?.cell_type   ?? 'python';
        document.getElementById('cellSqlConnection').value   = cell?.sql_connection ?? '';
        document.getElementById('sqlConnectionDiv').style.display =
            cell?.cell_type === 'sql' ? 'block' : 'none';
        document.querySelector('#cellModal .modal-title').textContent =
            cell ? 'Editar Célula' : 'Nova Célula';

        // Ativa os snippets sempre que o modal é aberto
        this._setupSnippetsListener();
    }

    _renderOutput(container, output) {
        if (!output) return;

        container.innerHTML = '';

        const isHtml =
            typeof output === 'string' &&
            (
                output.includes('<div') ||
                output.includes('<img') ||
                output.includes('<table') ||
                output.includes('<script')
            );

        if (!isHtml) {
            const pre = document.createElement('pre');
            pre.className = 'mb-0';
            pre.textContent = output;
            container.appendChild(pre);
            return;
        }

        container.innerHTML = output;

        container.querySelectorAll('script').forEach(oldScript => {
            const script = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => {
                script.setAttribute(attr.name, attr.value);
            });
            script.text = oldScript.text;
            oldScript.parentNode.replaceChild(script, oldScript);
        });
    }

    // ============================================================
    // SNIPPETS VIA TECLA TAB (Fase 1) – APENAS MARKDOWN
    // ============================================================

    _setupSnippetsListener() {
        const textarea = document.getElementById('cellContent');
        if (!textarea) return;
        if (this._boundSnippetHandler) {
            textarea.removeEventListener('keydown', this._boundSnippetHandler);
        }
        this._boundSnippetHandler = this._handleSnippetKeydown.bind(this);
        textarea.addEventListener('keydown', this._boundSnippetHandler);
    }

    _removeSnippetsListener() {
        const textarea = document.getElementById('cellContent');
        if (textarea && this._boundSnippetHandler) {
            textarea.removeEventListener('keydown', this._boundSnippetHandler);
            this._boundSnippetHandler = null;
        }
    }

    _handleSnippetKeydown(e) {
        // Só aplica snippets se o tipo de célula for Markdown
        const cellType = document.getElementById('cellType').value;
        if (cellType !== 'markdown') return;

        if (e.key !== 'Tab') return;
        const textarea = e.target;
        const start = textarea.selectionStart;
        const value = textarea.value;
        const beforeCursor = value.slice(0, start);
        const wordMatch = beforeCursor.match(/[\w#`]+$/);
        if (!wordMatch) return;
        const word = wordMatch[0];
        const snippet = this._getSnippet(word);
        if (snippet) {
            e.preventDefault();
            const newValue = value.slice(0, start - word.length) + snippet + value.slice(start);
            textarea.value = newValue;
            textarea.selectionStart = textarea.selectionEnd = start - word.length + snippet.length;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }

    _getSnippet(word) {
        const snippets = {
            '#': '# ',
            '##': '## ',
            '###': '### ',
            '####': '#### ',
            '```': '```python\n\n```',
            '|': '| Coluna 1 | Coluna 2 |\n|----------|----------|\n|          |          |',
            '- ': '- ',
            '1.': '1. ',
            'sql': '```sql\n\n```',
            'table': '| Nome | Valor |\n|------|-------|\n|      |       |',
            'mermaid': '```mermaid\ngraph TD\nA[Início] --> B{Fim?}\nB -->|Sim| C[Fim]\nB -->|Não| A\n```',
        };
        return snippets[word];
    }

    // ============================================================
    // RENDERIZAÇÃO DO MODAL DE EXECUÇÃO
    // ============================================================

    _renderOutputModal(data) {
        const logDiv = document.getElementById('execLogs');
        logDiv.innerHTML = '';

        const output = data.output || data.html || data.result || '';

        if (output) {
            this._renderOutput(logDiv, output);
            return;
        }

        if (data.error) {
            const pre = document.createElement('pre');
            pre.className = 'text-danger mb-0';
            pre.textContent = data.error;
            logDiv.appendChild(pre);
            return;
        }

        logDiv.innerHTML = `
            <div class="text-muted">
                Execução concluída sem saída.
            </div>
        `;
    }

    _showModalError(message) {
        const logDiv = document.getElementById('execLogs');
        const pre    = document.createElement('pre');
        pre.className   = 'text-danger mb-0';
        pre.textContent = message;
        logDiv.innerHTML = '';
        logDiv.appendChild(pre);
    }

    _setContainerLoading(on) {
        const container = document.getElementById('cellsContainer');
        if (!container || !on) return;
        container.innerHTML = `
            <div class="text-muted p-4 text-center">
                <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                Carregando células…
            </div>`;
    }

    _confirm(title, body) {
        return new Promise((resolve) => {
            let modalEl = document.getElementById('confirmModal');
            if (!modalEl) {
                modalEl = document.createElement('div');
                modalEl.id        = 'confirmModal';
                modalEl.className = 'modal fade';
                modalEl.tabIndex  = -1;
                modalEl.innerHTML = `
                    <div class="modal-dialog modal-dialog-centered modal-sm">
                        <div class="modal-content">
                            <div class="modal-header border-0 pb-0">
                                <h6 class="modal-title fw-semibold" id="confirmModalTitle"></h6>
                            </div>
                            <div class="modal-body pt-1" id="confirmModalBody"></div>
                            <div class="modal-footer border-0 pt-0">
                                <button class="btn btn-sm btn-secondary" id="confirmModalCancel">Cancelar</button>
                                <button class="btn btn-sm btn-danger"    id="confirmModalOk">Remover</button>
                            </div>
                        </div>
                    </div>`;
                document.body.appendChild(modalEl);
            }

            document.getElementById('confirmModalTitle').textContent = title;
            document.getElementById('confirmModalBody').textContent  = body;

            const modal     = bootstrap.Modal.getOrCreateInstance(modalEl);
            const okBtn     = document.getElementById('confirmModalOk');
            const cancelBtn = document.getElementById('confirmModalCancel');

            const cleanup = (result) => {
                okBtn.removeEventListener('click', onOk);
                cancelBtn.removeEventListener('click', onCancel);
                modalEl.removeEventListener('hidden.bs.modal', onCancel);
                modal.hide();
                resolve(result);
            };

            const onOk     = () => cleanup(true);
            const onCancel = () => cleanup(false);

            okBtn.addEventListener('click', onOk);
            cancelBtn.addEventListener('click', onCancel);
            modalEl.addEventListener('hidden.bs.modal', onCancel, { once: true });

            modal.show();
        });
    }
}