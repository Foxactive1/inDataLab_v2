// dataset.js - versão completa e otimizada para SQLite
class DatasetManager {
    constructor() {
        this.cachedDatasets = null; // cache para acesso rápido
        this.cachedSqlMetadata = {}; // cache de metadados SQL por ID
    }

    // ============================================================
    // CARREGAR E RENDERIZAR LISTA
    // ============================================================
    async loadDatasets() {
        if (!app.notebook.currentId) return;
        try {
            const data = await API.get(`/notebooks/${app.notebook.currentId}/datasets`);
            if (data.success) {
                this.cachedDatasets = data.data;
                this.renderList(data.data);
            }
        } catch (err) {
            app.toast('Erro ao carregar datasets', 'danger');
        }
    }

    renderList(datasets) {
    const container = document.getElementById('datasetsList');
    if (!datasets || datasets.length === 0) {
        container.innerHTML = '<div class="text-muted small">Nenhum dataset carregado. Arraste um arquivo ou clique em "Dataset".</div>';
        return;
    }

    container.innerHTML = datasets.map(ds => {
        // Determina o ícone conforme o tipo
        let icon = 'bi-database';
        if (ds.file_type === 'csv') icon = 'bi-filetype-csv';
        else if (ds.file_type === 'excel') icon = 'bi-file-earmark-excel';
        else if (ds.file_type === 'json') icon = 'bi-filetype-json';
        else if (ds.file_type === 'db' || ds.is_sql_database) icon = 'bi-database';

        // Monta a linha de informações (metadados)
        let infoHtml = '';
        const isSqlite = (ds.file_type === 'db' || ds.is_sql_database);
        
        if (isSqlite) {
            const metadata = ds.extra_metadata || {};
            const tables = metadata.tables || [];
            if (tables.length > 0) {
                const tableNames = tables.map(t => t.name).slice(0, 3).join(', ');
                const more = tables.length > 3 ? ` +${tables.length - 3}` : '';
                const totalRows = tables.reduce((sum, t) => sum + (t.rows || 0), 0);
                const rowsInfo = totalRows > 0 ? ` • ${totalRows} registros` : '';
                infoHtml = `<small class="text-muted d-block">📊 ${tables.length} tabela(s): ${escapeHtml(tableNames)}${more}${rowsInfo}</small>`;
            } else {
                infoHtml = `<small class="text-muted d-block">🗄️ Banco SQLite (sem metadados)</small>`;
            }
        } else {
            const rows = ds.rows || '?';
            const cols = ds.columns || '?';
            infoHtml = `<small class="text-muted d-block">${rows} linhas × ${cols} colunas</small>`;
        }

        return `
            <div class="dataset-item" data-dataset-id="${ds.id}">
                <div>
                    <i class="bi ${icon} me-1"></i>
                    <strong>${escapeHtml(ds.filename)}</strong>
                    ${infoHtml}
                </div>
                <div class="d-flex gap-1">
                    <!-- Botão de visualizar dados: só aparece se NÃO for SQLite -->
                    ${!isSqlite ? `
                        <button class="btn btn-sm btn-outline-secondary" 
                                onclick="app.dataset.viewData(${ds.id})" 
                                title="Visualizar dados">
                            <i class="bi bi-eye"></i>
                        </button>
                    ` : ''}
                    
                    <!-- Botões específicos para SQLite -->
                    ${isSqlite ? `
                        <button class="btn btn-sm btn-outline-info" 
                                onclick="app.dataset.inspectSql(${ds.id})" 
                                title="Inspecionar estrutura SQL">
                            <i class="bi bi-database-gear"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-success" 
                                onclick="app.dataset.setAsSqlConnection(${ds.id})" 
                                title="Definir como conexão SQL padrão do notebook">
                            <i class="bi bi-plug"></i>
                        </button>
                    ` : ''}
                    
                    <!-- Excluir (sempre disponível) -->
                    <button class="btn btn-sm btn-outline-danger" 
                            onclick="app.dataset.deleteDataset(${ds.id})" 
                            title="Excluir dataset">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

    // ============================================================
    // UPLOAD DE DATASET
    // ============================================================
    async upload(file = null) {
        if (!app.notebook.currentId) return;
        const uploadFile = file || document.getElementById('datasetFile').files[0];
        if (!uploadFile) {
            app.toast('Selecione um arquivo', 'warning');
            return;
        }
        const formData = new FormData();
        formData.append('file', uploadFile);
        try {
            const data = await API.upload(`/notebooks/${app.notebook.currentId}/datasets`, formData);
            if (data.success) {
                await this.loadDatasets();  // recarrega a lista
                app.toast(`Dataset "${uploadFile.name}" importado`, 'success');
                bootstrap.Modal.getInstance(document.getElementById('datasetUploadModal')).hide();
            } else {
                app.toast('Erro: ' + data.error, 'danger');
            }
        } catch (err) {
            app.toast('Falha no upload', 'danger');
        }
    }

    // ============================================================
    // VISUALIZAR DADOS (CSV, Excel, JSON) – NÃO PARA SQLITE
    // ============================================================
    async viewData(id) {
        // Primeiro, verifica se é SQLite (para não tentar visualizar)
        const ds = this.getDatasetById(id);
        if (ds && (ds.file_type === 'db' || ds.is_sql_database)) {
            app.toast('Bancos SQLite não permitem visualização direta. Use células SQL para consultar.', 'info');
            return;
        }

        try {
            const data = await API.get(`/notebooks/${app.notebook.currentId}/datasets/${id}/data`);
            if (data.success) {
                const preview = data.data.slice(0, 20);
                const html = this.buildTablePreview(preview);
                const modal = new bootstrap.Modal(document.getElementById('previewModal'));
                document.getElementById('previewModalBody').innerHTML = html;
                modal.show();
            } else {
                app.toast('Erro: ' + (data.error || 'Dados não disponíveis'), 'danger');
            }
        } catch (err) {
            console.error(err);
            app.toast('Erro ao visualizar dados', 'danger');
        }
    }

    buildTablePreview(rows) {
        if (!rows || rows.length === 0) return '<p class="text-muted">Nenhum dado para exibir.</p>';
        const keys = Object.keys(rows[0]);
        return `
            <div style="overflow-x: auto;">
                <table class="table table-sm table-bordered table-striped">
                    <thead class="table-secondary">
                        <tr>${keys.map(k => `<th>${escapeHtml(k)}</th>`).join('')}</tr>
                    </thead>
                    <tbody>
                        ${rows.map(row => `
                            <tr>${keys.map(k => `<td>${escapeHtml(String(row[k] ?? ''))}</td>`).join('')}</tr>
                        `).join('')}
                    </tbody>
                </table>
                ${rows.length === 20 ? '<p class="text-muted small">Mostrando apenas as 20 primeiras linhas.</p>' : ''}
            </div>
        `;
    }

    // ============================================================
    // INSPECIONAR SQLITE (listar tabelas, colunas, linhas e estatísticas)
    // ============================================================
    // ============================================================
// INSPECIONAR SQLITE (listar tabelas, colunas, linhas e estatísticas)
// ============================================================
	async inspectSql(id) {
    try {
        // Verifica cache primeiro
        if (this.cachedSqlMetadata[id]) {
            this.showSqlInspectModal(id, this.cachedSqlMetadata[id]);
            return;
        }

        const data = await API.get(`/notebooks/${app.notebook.currentId}/datasets/${id}/inspect_sql`);
        if (data.success && data.data && data.data.tables) {
            // Armazena em cache
            this.cachedSqlMetadata[id] = data.data;
            this.showSqlInspectModal(id, data.data);
        } else {
            app.toast('Nenhuma informação de estrutura disponível.', 'warning');
        }
    } catch (err) {
        console.error(err);
        app.toast('Erro na inspeção SQL', 'danger');
    }
}

	showSqlInspectModal(datasetId, data) {
    const ds = this.getDatasetById(datasetId);
    const tables = data.tables || [];
    const totalTables = tables.length;
    const totalRecords = tables.reduce((sum, t) => sum + (t.rows || 0), 0);
    const totalColumns = tables.reduce((sum, t) => sum + (t.columns?.length || 0), 0);

    let tablesHtml = '';
    if (tables.length === 0) {
        tablesHtml = '<p class="text-muted text-center p-3">Nenhuma tabela encontrada neste banco.</p>';
    } else {
        tablesHtml = tables.map((t, idx) => {
            // Processa colunas (corrigido para objetos)
            const columnsHtml = (t.columns || []).map(col => {
                let columnName = '?';
                let columnType = '-';

                if (typeof col === 'string') {
                    columnName = col;
                } else if (col && typeof col === 'object') {
                    columnName = col.name || col.column_name || '?';
                    columnType = col.type || col.data_type || '-';
                }

                return `
                    <tr>
                        <td><code>${escapeHtml(columnName)}</code></td>
                        <td><span class="text-muted small">${escapeHtml(columnType)}</span></td>
                    </tr>
                `;
            }).join('');

            return `
                <div class="card mb-3 border-info">
                    <div class="card-header bg-info bg-opacity-10">
                        <div class="row align-items-center">
                            <div class="col-md-6">
                                <h6 class="mb-0">
                                    <i class="bi bi-table me-2"></i>
                                    ${escapeHtml(t.name)}
                                </h6>
                            </div>
                            <div class="col-md-6 text-end">
                                <small class="badge bg-info me-2">
                                    <i class="bi bi-rows me-1"></i>${t.rows || 0} registros
                                </small>
                                <small class="badge bg-secondary">
                                    <i class="bi bi-columns me-1"></i>${t.columns?.length || 0} colunas
                                </small>
                            </div>
                        </div>
                    </div>
                    <div class="card-body p-0">
                        <!-- NOVO: Nome da tabela em destaque -->
                        <div class="fw-bold mt-2 mb-2 ms-2" style="font-size: 1.1rem;">
                            📌 Tabela: <span style="color: #d63384; font-weight: 600;">${(t.name || t.table_name || 'Sem nome')}</span>
                        </div>
                        <table class="table table-sm table-hover mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th style="width: 35%;">Coluna</th>
                                    <th style="width: 65%;">Tipo</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${columnsHtml}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Cria o modal (restante igual ao seu original, sem alterações)
    let modalHtml = `
        <div class="modal fade" id="sqlInspectModal${datasetId}" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header bg-primary bg-opacity-10 border-bottom">
                        <div>
                            <h5 class="modal-title mb-0">
                                <i class="bi bi-database me-2"></i>
                                Inspeção do Banco: ${escapeHtml(ds?.filename || 'Unknown')}
                            </h5>
                            <small class="text-muted d-block mt-1">Visualize a estrutura completa do banco de dados SQLite</small>
                        </div>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- Resumo Estatístico -->
                        <div class="row mb-4">
                            <div class="col-md-4">
                                <div class="card border-0 bg-light">
                                    <div class="card-body text-center">
                                        <div class="fs-3 fw-bold text-primary">${totalTables}</div>
                                        <div class="small text-muted">Tabela${totalTables !== 1 ? 's' : ''}</div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card border-0 bg-light">
                                    <div class="card-body text-center">
                                        <div class="fs-3 fw-bold text-success">${totalRecords.toLocaleString()}</div>
                                        <div class="small text-muted">Registros</div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card border-0 bg-light">
                                    <div class="card-body text-center">
                                        <div class="fs-3 fw-bold text-info">${totalColumns}</div>
                                        <div class="small text-muted">Colunas</div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <hr class="my-4">

                        <!-- Lista de Tabelas -->
                        <h6 class="mb-3">
                            <i class="bi bi-list-ul me-2"></i>Tabelas (${totalTables})
                        </h6>
                        ${tablesHtml}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Fechar</button>
                        <button type="button" class="btn btn-primary" onclick="app.dataset.setAsSqlConnection(${datasetId})">
                            <i class="bi bi-plug me-2"></i>Usar como Conexão
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove modal anterior se existir
    const oldModal = document.getElementById(`sqlInspectModal${datasetId}`);
    if (oldModal) oldModal.remove();

    // Injeta novo modal no DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Mostra o modal
    const modalElement = document.getElementById(`sqlInspectModal${datasetId}`);
    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    // Limpa o modal quando fechado
    modalElement.addEventListener('hidden.bs.modal', () => {
        modalElement.remove();
    });
}
    // ============================================================
    // DEFINIR COMO CONEXÃO SQL PADRÃO DO NOTEBOOK
    // ============================================================
    async setAsSqlConnection(id) {
        try {
            const data = await API.post(`/notebooks/${app.notebook.currentId}/datasets/${id}/set_as_sql_connection`, {});
            if (data.success) {
                app.toast('Conexão SQL definida como padrão para este notebook', 'success');
                await this.loadDatasets();  // recarrega para atualizar eventual indicador visual
            } else {
                app.toast('Erro: ' + (data.error || 'Falha ao definir conexão'), 'danger');
            }
        } catch (err) {
            console.error(err);
            app.toast('Erro ao definir conexão', 'danger');
        }
    }

    // ============================================================
    // EXCLUIR DATASET (com confirmação)
    // ============================================================
    async deleteDataset(id) {
        const ds = this.getDatasetById(id);
        const filename = ds?.filename || 'dataset';
        if (!confirm(`Remover "${filename}" permanentemente? Esta ação não pode ser desfeita.`)) return;
        try {
            const data = await API.delete(`/notebooks/${app.notebook.currentId}/datasets/${id}`);
            if (data.success) {
                // Limpa cache se existir
                delete this.cachedSqlMetadata[id];
                await this.loadDatasets();
                app.toast('Dataset removido com sucesso', 'success');
            } else {
                app.toast('Erro: ' + (data.error || 'Falha ao excluir'), 'danger');
            }
        } catch (err) {
            console.error(err);
            app.toast('Erro ao excluir dataset', 'danger');
        }
    }

    // ============================================================
    // AUXILIAR: obter dataset por ID a partir do cache
    // ============================================================
    getDatasetById(id) {
        if (!this.cachedDatasets) return null;
        return this.cachedDatasets.find(ds => ds.id === id);
    }

    // ============================================================
    // AUXILIAR: escapar HTML para evitar injeção
    // ============================================================
    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Função global de escape HTML (se não existir em outro lugar)
if (typeof escapeHtml === 'undefined') {
    window.escapeHtml = (text) => {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
}
