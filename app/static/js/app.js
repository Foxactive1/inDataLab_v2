class App {
    constructor() {
        this.notebook = new NotebookManager();
        this.cell     = new CellManager();
        this.chat     = new ChatManager();
        this.dataset  = new DatasetManager();
        this._init();
    }

    // ============================================================
    // INICIALIZAÇÃO
    // ============================================================
    _init() {
        // ThemeManager já se inicializa sozinho (theme-manager.js)
        // setupTheme() apenas conecta o botão — sem duplicar lógica
        this._setupThemeButton();
        this._setupSidebar();
        this._setupDragDrop();
        this._setupEventListeners();
        this._setupKeyboardShortcuts();
        this.notebook.load();
    }

    // ============================================================
    // TEMA — apenas delega ao ThemeManager existente
    // ============================================================
    _setupThemeButton() {
        // O ThemeManager (theme-manager.js) já inicializa e atualiza o botão.
        // Este método garante que o clique esteja conectado caso o script
        // carregue antes do DOMContentLoaded terminar de executar o inline script.
        const btn = document.getElementById('themeToggleBtn');
        if (btn && window.themeManager) {
            // Remove listeners duplicados trocando pelo clone
            const fresh = btn.cloneNode(true);
            btn.parentNode.replaceChild(fresh, btn);
            fresh.addEventListener('click', () => window.themeManager.toggleTheme());
        }
    }

    // ============================================================
    // SIDEBAR
    // ============================================================
    _setupSidebar() {
        const sidebar     = document.getElementById('notebooksSidebar');
        const toggleBtn   = document.getElementById('toggleSidebarBtn');
        const mobileBtn   = document.getElementById('openSidebarMobileBtn');
        const closeBtn    = document.getElementById('closeSidebarBtnMobile');

        // Cria overlay se ainda não existir
        let overlay = document.querySelector('.sidebar-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay';
            document.body.appendChild(overlay);
        }

        const open  = () => { sidebar.classList.add('show');    overlay.classList.add('show'); };
        const close = () => { sidebar.classList.remove('show'); overlay.classList.remove('show'); };

        if (toggleBtn) toggleBtn.addEventListener('click', () => sidebar.classList.toggle('collapsed'));
        if (mobileBtn) mobileBtn.addEventListener('click', open);
        if (closeBtn)  closeBtn.addEventListener('click', close);
        overlay.addEventListener('click', close);

        // Fecha sidebar mobile ao pressionar Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && sidebar.classList.contains('show')) close();
        });
    }

    // ============================================================
    // DRAG & DROP DE DATASET — com feedback visual
    // ============================================================
    _setupDragDrop() {
        const dropZone = document.getElementById('datasetsFooterContainer');
        if (!dropZone) return;

        let dragCounter = 0; // contador para evitar flicker ao passar sobre filhos

        dropZone.addEventListener('dragenter', (e) => {
            e.preventDefault();
            dragCounter++;
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', () => {
            dragCounter--;
            if (dragCounter === 0) dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault(); // necessário para permitir o drop
            e.dataTransfer.dropEffect = 'copy';
        });

        dropZone.addEventListener('drop', async (e) => {
            e.preventDefault();
            dragCounter = 0;
            dropZone.classList.remove('drag-over');

            const file = e.dataTransfer.files[0];
            if (!file) return;

            // Valida tipo antes de enviar
            const allowed = ['csv', 'txt', 'xlsx', 'xls', 'json', 'db', 'sqlite', 'sqlite3'];
            const ext = file.name.split('.').pop().toLowerCase();
            if (!allowed.includes(ext)) {
                this.toast(`Tipo de arquivo não suportado: .${ext}`, 'warning');
                return;
            }

            await this.dataset.upload(file);
        });
    }

    // ============================================================
    // EVENT LISTENERS GERAIS
    // ============================================================
    _setupEventListeners() {
        // Toolbar principal
        document.getElementById('refreshCellsBtn')
            ?.addEventListener('click', () => this.cell.loadCells());

        document.getElementById('addCellBtn')
            ?.addEventListener('click', () => this.cell.openNewModal());

        // Chat desktop
        const desktopInput  = document.getElementById('copilotInput');
        const desktopSend   = document.getElementById('copilotSendBtn');
        const desktopClear  = document.getElementById('copilotClearBtn');

        desktopSend?.addEventListener('click', () => {
            this.chat.sendMessage(desktopInput.value);
        });

        desktopInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.chat.sendMessage(desktopInput.value);
            }
        });

        desktopClear?.addEventListener('click', () => this.chat.clear());

        // Chat mobile
        const mobileModal = document.getElementById('chatMobileModal');
        if (mobileModal) {
            const mobileInput = document.getElementById('copilotInputMobile');
            const mobileSend  = document.getElementById('copilotSendMobileBtn');
            const mobileClear = document.getElementById('copilotClearMobileBtn');

            mobileModal.addEventListener('shown.bs.modal', () => mobileInput?.focus());

            mobileSend?.addEventListener('click', () => {
                this.chat.sendMessage(mobileInput.value, 'copilotMessagesMobile');
            });

            mobileInput?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.chat.sendMessage(mobileInput.value, 'copilotMessagesMobile');
                }
            });

            mobileClear?.addEventListener('click', () => this.chat.clear('copilotMessagesMobile'));
        }

        // FAB — abre chat mobile
        document.getElementById('fabChatBtn')?.addEventListener('click', () => {
            const modal = document.getElementById('chatMobileModal');
            if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();
        });

        // Modal de célula: mostrar/esconder campo SQL
        const cellTypeSelect = document.getElementById('cellType');
        const sqlDiv         = document.getElementById('sqlConnectionDiv');
        if (cellTypeSelect && sqlDiv) {
            cellTypeSelect.addEventListener('change', () => {
                sqlDiv.style.display = cellTypeSelect.value === 'sql' ? 'block' : 'none';
            });
        }
    }

    // ============================================================
    // ATALHOS DE TECLADO
    // ============================================================
    _setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignora quando o foco está em inputs/textareas/selects
            const tag = document.activeElement?.tagName;
            const inInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag);

            // Ctrl/Cmd + Enter — executa célula em foco (se houver)
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const focused = document.querySelector('.cell-card:focus-within');
                if (focused) {
                    const cellId = focused.dataset.cellId;
                    if (cellId) {
                        e.preventDefault();
                        this.cell.executeCell(Number(cellId));
                    }
                }
                return;
            }

            // Atalhos que não devem funcionar dentro de inputs
            if (inInput) return;

            switch (e.key) {
                // N — novo notebook
                case 'n':
                    if (!e.ctrlKey && !e.metaKey) {
                        e.preventDefault();
                        this.notebook.openNewModal();
                    }
                    break;

                // C — nova célula (requer notebook selecionado)
                case 'c':
                    if (!e.ctrlKey && !e.metaKey && this.notebook.currentId) {
                        e.preventDefault();
                        this.cell.openNewModal();
                    }
                    break;

                // R — atualizar células
                case 'r':
                    if (!e.ctrlKey && !e.metaKey && this.notebook.currentId) {
                        e.preventDefault();
                        this.cell.loadCells();
                    }
                    break;

                // ? — exibir ajuda de atalhos
                case '?':
                    this._showShortcutsHelp();
                    break;
            }
        });
    }

    // ============================================================
    // TOAST — mensagem de feedback
    // ============================================================
    toast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${type} border-0`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');

        // Usa textContent para evitar XSS — não interpreta HTML na mensagem
        const body = document.createElement('div');
        body.className = 'toast-body';
        body.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close me-2 m-auto';
        closeBtn.setAttribute('data-bs-dismiss', 'toast');

        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex';
        wrapper.appendChild(body);
        wrapper.appendChild(closeBtn);

        toastEl.appendChild(wrapper);
        container.appendChild(toastEl);

        const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 3500 });
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    }

    // ============================================================
    // AJUDA DE ATALHOS
    // ============================================================
    _showShortcutsHelp() {
        this.toast('Atalhos: N = Novo notebook | C = Nova célula | R = Recarregar | Ctrl+Enter = Executar célula', 'info');
    }
}

// ============================================================
// INICIALIZAÇÃO — aguarda DOM completo
// ============================================================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { window.app = new App(); });
} else {
    window.app = new App();
}
