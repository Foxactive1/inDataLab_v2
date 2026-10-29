// chat.js
class ChatManager {
    constructor() {
        // IDs dos dois containers de exibição
        this._containers = [
            'copilotMessages',
            'copilotMessagesMobile',
        ];

        // Histórico em memória — fonte única de verdade para ambos os containers
        this._history = [];

        // Guarda contra envios simultâneos
        this._sending = false;

        // Mensagem inicial exibida antes de qualquer interação
        this._welcomeMessage = 'Olá! Posso ajudar com código, explicar células ou sugerir análises.';

        this._renderAll();
    }

    // ============================================================
    // ENVIAR MENSAGEM
    // ============================================================
    async sendMessage(message) {
        const text = (message || '').trim();

        if (!text) return;

        if (!app.notebook.currentId) {
            app.toast('Selecione um notebook primeiro.', 'warning');
            return;
        }

        if (this._sending) {
            app.toast('Aguarde a resposta anterior.', 'warning');
            return;
        }

        this._sending = true;
        this._clearInputs();

        // Registra mensagem do usuário no histórico e renderiza
        this._pushMessage('user', text);

        // Indicador de "pensando"
        const thinkingId = this._pushThinking();

        try {
            const data = await API.post(
                `/copilot/notebooks/${app.notebook.currentId}/chat`,
                { message: text }
            );

            this._removeThinking(thinkingId);

            if (data.success) {
                this._pushMessage('assistant', data.response, true /* markdown */);
            } else {
                this._pushMessage('assistant-error', data.error || 'Erro desconhecido');
            }

        } catch (err) {
            this._removeThinking(thinkingId);
            this._pushMessage('assistant-error', 'Erro de conexão: ' + err.message);
        } finally {
            this._sending = false;
        }
    }

    // ============================================================
    // LIMPAR HISTÓRICO
    // ============================================================
    async clear() {
        if (!app.notebook.currentId) return;

        try {
            await API.delete(`/copilot/notebooks/${app.notebook.currentId}/clear_chat`);
            this._history = [];
            this._renderAll();
            app.toast('Histórico do chat removido.', 'info');
        } catch (err) {
            app.toast('Erro ao limpar histórico: ' + err.message, 'danger');
        }
    }

    // ============================================================
    // HISTÓRICO — adicionar mensagem e sincronizar
    // ============================================================

    /** Adiciona entrada ao histórico e re-renderiza todos os containers */
    _pushMessage(role, content, isMarkdown = false) {
        const entry = { role, content, isMarkdown, id: Date.now() + Math.random() };
        this._history.push(entry);
        this._renderAll();
        return entry.id;
    }

    /** Adiciona indicador de "pensando" e retorna um ID para remoção posterior */
    _pushThinking() {
        const id = 'thinking-' + Date.now();
        const entry = { role: 'thinking', content: '🤔 pensando...', isMarkdown: false, id };
        this._history.push(entry);
        this._renderAll();
        return id;
    }

    /** Remove o indicador de "pensando" pelo ID */
    _removeThinking(id) {
        this._history = this._history.filter(e => e.id !== id);
        this._renderAll();
    }

    // ============================================================
    // RENDERIZAÇÃO — sincroniza desktop e mobile
    // ============================================================

    /** Re-renderiza todos os containers a partir do histórico em memória */
    _renderAll() {
        this._containers.forEach(containerId => {
            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = '';
            const fragment = document.createDocumentFragment();

            // Mensagem de boas-vindas quando histórico está vazio
            if (this._history.length === 0) {
                fragment.appendChild(this._buildBubble('assistant', this._welcomeMessage, false));
            } else {
                this._history.forEach(entry => {
                    fragment.appendChild(
                        this._buildBubble(entry.role, entry.content, entry.isMarkdown)
                    );
                });
            }

            container.appendChild(fragment);
            container.scrollTop = container.scrollHeight;
        });
    }

    /** Cria o elemento DOM de uma bolha de mensagem */
    _buildBubble(role, content, isMarkdown) {
        const div = document.createElement('div');

        switch (role) {
            case 'user':
                div.className = 'msg-user';
                div.textContent = content; // usuário: sempre textContent (sem XSS)
                break;

            case 'assistant':
                div.className = 'msg-assistant';
                if (isMarkdown) {
                    // Resposta da IA em markdown — marked é a fonte, não input do usuário
                    div.innerHTML = marked.parse(content);
                } else {
                    div.textContent = content;
                }
                break;

            case 'assistant-error':
                div.className = 'msg-assistant text-danger';
                div.textContent = content;
                break;

            case 'thinking':
                div.className = 'msg-assistant text-muted fst-italic';
                div.textContent = content;
                break;

            default:
                div.textContent = content;
        }

        return div;
    }

    // ============================================================
    // INPUTS — limpa ambos os campos após envio
    // ============================================================
    _clearInputs() {
        const desktop = document.getElementById('copilotInput');
        const mobile  = document.getElementById('copilotInputMobile');
        if (desktop) desktop.value = '';
        if (mobile)  mobile.value  = '';
    }
}
