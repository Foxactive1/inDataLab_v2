class NotebookManager {
    constructor() {
        this.currentId  = null;
        this.page       = 1;
        this._loading   = false;

        // Delegação de eventos — um único listener no container
        this._setupDelegation();
    }

    // ============================================================
    // DELEGAÇÃO DE EVENTOS
    // Substitui todos os onclick="..." inline gerados no HTML
    // ============================================================
    _setupDelegation() {
        const list = document.getElementById('notebooksList');
        if (!list) return;

        list.addEventListener('click', (e) => {
            // Botão editar
            const editBtn = e.target.closest('[data-action="edit"]');
            if (editBtn) {
                e.stopPropagation();
                this.edit(Number(editBtn.dataset.id));
                return;
            }

            // Botão excluir
            const deleteBtn = e.target.closest('[data-action="delete"]');
            if (deleteBtn) {
                e.stopPropagation();
                this.delete(Number(deleteBtn.dataset.id));
                return;
            }

            // Clique no item (selecionar notebook)
            const item = e.target.closest('[data-action="select"]');
            if (item) this.select(Number(item.dataset.id));
        });

        // Paginação — delegada no container pai
        const pagEl = document.getElementById('notebookPagination');
        if (pagEl) {
            pagEl.addEventListener('click', (e) => {
                const link = e.target.closest('[data-page]');
                if (link) {
                    e.preventDefault();
                    this.load(Number(link.dataset.page));
                }
            });
        }
    }

    // ============================================================
    // CARREGAR LISTA
    // ============================================================
    async load(page = 1) {
        if (this._loading) return;
        this._loading = true;
        this.page = page;

        this._setListLoading(true);

        try {
            const data = await API.get(`/notebooks?page=${page}&per_page=8`);
            if (data.success) {
                this.renderList(data.data.notebooks);
                this.renderPagination(data.data.pagination);
            } else {
                app.toast('Não foi possível carregar os notebooks.', 'warning');
            }
        } catch (err) {
            app.toast('Erro ao carregar notebooks: ' + err.message, 'danger');
        } finally {
            this._loading = false;
            this._setListLoading(false);
        }
    }

    // ============================================================
    // RENDERIZAR LISTA
    // ============================================================
    renderList(notebooks) {
        const container = document.getElementById('notebooksList');

        if (!notebooks || notebooks.length === 0) {
            container.innerHTML = `
                <div class="p-4 text-center text-muted">
                    <i class="bi bi-journal-x fs-3 d-block mb-2"></i>
                    Nenhum notebook criado.<br>
                    <small>Clique em <strong>+</strong> para começar.</small>
                </div>`;
            return;
        }

        // Usa fragment para evitar múltiplos reflows
        const fragment = document.createDocumentFragment();

        notebooks.forEach(nb => {
            const isActive = this.currentId === nb.id;
            const item = document.createElement('div');
            item.className = `list-group-item list-group-item-action d-flex justify-content-between align-items-center${isActive ? ' active' : ''}`;
            item.dataset.action = 'select';
            item.dataset.id     = nb.id;
            item.style.cursor   = 'pointer';

            // Texto
            const textDiv = document.createElement('div');
            textDiv.className = 'text-truncate me-2';

            const title = document.createElement('div');
            title.className  = 'fw-semibold text-truncate';
            title.textContent = nb.title;

            const desc = document.createElement('small');
            desc.className   = 'text-truncate d-block';
            desc.style.maxWidth = '180px';
            desc.textContent = nb.description || 'Sem descrição';
            if (!isActive) desc.classList.add('text-muted');

            textDiv.appendChild(title);
            textDiv.appendChild(desc);

            // Botões de ação
            const actions = document.createElement('div');
            actions.className = 'd-flex gap-1 flex-shrink-0';

            const editBtn = document.createElement('button');
            editBtn.className = 'btn btn-sm btn-light rounded-circle';
            editBtn.title     = 'Editar notebook';
            editBtn.dataset.action = 'edit';
            editBtn.dataset.id     = nb.id;
            editBtn.innerHTML = '<i class="bi bi-pencil"></i>';

            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn-sm btn-light rounded-circle';
            delBtn.title     = 'Excluir notebook';
            delBtn.dataset.action = 'delete';
            delBtn.dataset.id     = nb.id;
            delBtn.innerHTML = '<i class="bi bi-trash"></i>';

            actions.appendChild(editBtn);
            actions.appendChild(delBtn);

            item.appendChild(textDiv);
            item.appendChild(actions);
            fragment.appendChild(item);
        });

        container.innerHTML = '';
        container.appendChild(fragment);
    }

    // ============================================================
    // RENDERIZAR PAGINAÇÃO
    // ============================================================
    renderPagination(pagination) {
        const { page, pages } = pagination;
        const pagEl = document.getElementById('notebookPagination');
        if (!pagEl) return;

        if (pages <= 1) { pagEl.innerHTML = ''; return; }

        const fragment = document.createDocumentFragment();

        for (let i = 1; i <= pages; i++) {
            const li = document.createElement('li');
            li.className = `page-item${i === page ? ' active' : ''}`;

            const a = document.createElement('a');
            a.className    = 'page-link';
            a.href         = '#';
            a.textContent  = i;
            a.dataset.page = i;

            li.appendChild(a);
            fragment.appendChild(li);
        }

        pagEl.innerHTML = '';
        pagEl.appendChild(fragment);
    }

    // ============================================================
    // ABRIR MODAL — NOVO NOTEBOOK
    // ============================================================
    openNewModal() {
        this._fillModal(null);
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('notebookModal')
        ).show();
    }

    // ============================================================
    // SELECIONAR NOTEBOOK
    // ============================================================
    async select(id) {
        try {
            const data = await API.get(`/notebooks/${id}`);
            if (!data.success) {
                app.toast('Não foi possível carregar o notebook.', 'warning');
                return;
            }

            // Só atualiza currentId após confirmar sucesso da API
            this.currentId = id;

            const nb = data.data.notebook;
            document.getElementById('selectedNotebookTitle').textContent = nb.title;
            document.getElementById('selectedNotebookDesc').textContent  = nb.description || 'Sem descrição';
            document.getElementById('refreshCellsBtn').disabled = false;
            document.getElementById('addCellBtn').disabled      = false;

            // Recarrega lista para refletir item ativo
            this.renderList(
                document.getElementById('notebooksList')
                    .__notebooks || []
            );
            await this.load(this.page);

            app.cell.loadCells();
            app.dataset.loadDatasets();

        } catch (err) {
            app.toast('Erro ao selecionar notebook: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // EDITAR NOTEBOOK
    // ============================================================
    async edit(id) {
        try {
            const data = await API.get(`/notebooks/${id}`);
            if (!data.success) {
                app.toast('Não foi possível carregar o notebook.', 'warning');
                return;
            }
            this._fillModal(data.data.notebook);
            bootstrap.Modal.getOrCreateInstance(
                document.getElementById('notebookModal')
            ).show();
        } catch (err) {
            app.toast('Erro ao carregar notebook: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // SALVAR (criar ou editar)
    // ============================================================
    async save() {
        const id    = document.getElementById('notebookId').value;
        const title = document.getElementById('notebookTitle').value.trim();

        // Validação client-side
        if (!title) {
            document.getElementById('notebookTitle').focus();
            app.toast('O título do notebook é obrigatório.', 'warning');
            return;
        }

        const payload = {
            title,
            description:            document.getElementById('notebookDesc').value.trim(),
            is_public:              document.getElementById('notebookPublic').checked,
            kernel_type:            document.getElementById('notebookKernel').value,
            default_sql_connection: document.getElementById('notebookSqlConnection').value.trim()
        };

        const saveBtn = document.querySelector('#notebookModal .btn-primary');
        if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Salvando…'; }

        try {
            const method = id ? 'put' : 'post';
            const url    = id ? `/notebooks/${id}` : '/notebooks';
            const data   = await API[method](url, payload);

            if (data.success) {
                bootstrap.Modal.getInstance(
                    document.getElementById('notebookModal')
                )?.hide();

                await this.load(this.page);
                if (id && this.currentId == id) await this.select(Number(id));
                app.toast(`Notebook ${id ? 'atualizado' : 'criado'} com sucesso.`, 'success');
            } else {
                app.toast('Erro: ' + (data.error || data.message || 'Erro desconhecido'), 'danger');
            }
        } catch (err) {
            app.toast('Falha ao salvar: ' + err.message, 'danger');
        } finally {
            if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Salvar'; }
        }
    }

    // ============================================================
    // EXCLUIR NOTEBOOK — usa modal de confirmação Bootstrap
    // ============================================================
    async delete(id) {
        const confirmed = await this._confirm(
            'Excluir notebook?',
            'Esta ação é permanente e não pode ser desfeita.'
        );
        if (!confirmed) return;

        try {
            const data = await API.delete(`/notebooks/${id}`);

            if (data.success) {
                app.toast('Notebook excluído.', 'info');

                if (this.currentId === id) this._clearWorkspace();
                await this.load(this.page);
            } else {
                app.toast('Erro ao excluir: ' + (data.error || 'Erro desconhecido'), 'danger');
            }
        } catch (err) {
            app.toast('Falha ao excluir: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // HELPERS PRIVADOS
    // ============================================================

    /** Preenche o modal com dados de um notebook (ou reseta para novo) */
    _fillModal(nb) {
        document.getElementById('notebookId').value              = nb?.id            ?? '';
        document.getElementById('notebookTitle').value           = nb?.title          ?? '';
        document.getElementById('notebookDesc').value            = nb?.description    ?? '';
        document.getElementById('notebookPublic').checked        = nb?.is_public      ?? false;
        document.getElementById('notebookKernel').value          = nb?.kernel_type    ?? 'python3';
        document.getElementById('notebookSqlConnection').value   = nb?.default_sql_connection ?? '';
        document.querySelector('#notebookModal .modal-title')
            .textContent = nb ? 'Editar Notebook' : 'Novo Notebook';
    }

    /** Limpa a área principal ao desselecionar/excluir notebook ativo */
    _clearWorkspace() {
        this.currentId = null;
        document.getElementById('selectedNotebookTitle').textContent = 'Selecione um notebook';
        document.getElementById('selectedNotebookDesc').textContent  = '—';
        document.getElementById('refreshCellsBtn').disabled = true;
        document.getElementById('addCellBtn').disabled      = true;
        document.getElementById('cellsContainer').innerHTML =
            '<div class="text-muted p-4 text-center">📓 Selecione ou crie um notebook para começar.</div>';
        document.getElementById('datasetsList').innerHTML =
            '<div class="text-muted small">Nenhum dataset carregado.</div>';
    }

    /** Indicador de loading na lista */
    _setListLoading(on) {
        const container = document.getElementById('notebooksList');
        if (!container) return;
        if (on) {
            container.innerHTML = `
                <div class="p-3 text-center text-muted">
                    <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                    Carregando…
                </div>`;
        }
    }

    /**
     * Modal de confirmação Bootstrap — substitui confirm() nativo.
     * Retorna Promise<boolean>.
     */
    _confirm(title, body) {
        return new Promise((resolve) => {
            // Reutiliza ou cria o modal de confirmação
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
                                <button class="btn btn-sm btn-danger"    id="confirmModalOk">Excluir</button>
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
