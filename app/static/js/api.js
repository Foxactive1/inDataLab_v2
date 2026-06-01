class API {
    static base = '/api';
    static TIMEOUT_MS = 30000; // 30s — ajuste conforme necessidade

    // ============================================================
    // MÉTODO BASE — toda requisição passa por aqui
    // ============================================================
    static async _request(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.TIMEOUT_MS);

        try {
            const res = await fetch(`${this.base}${endpoint}`, {
                ...options,
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            // Erros HTTP (4xx, 5xx) — servidor respondeu mas com erro
            if (!res.ok) {
                let errorMessage = `Erro HTTP ${res.status}`;
                try {
                    const errorBody = await res.json();
                    errorMessage = errorBody.error || errorBody.message || errorMessage;
                } catch {
                    // Corpo não é JSON (ex: HTML de erro do servidor) — mantém mensagem genérica
                }
                throw new APIError(errorMessage, res.status);
            }

            // Resposta vazia (ex: 204 No Content)
            if (res.status === 204 || res.headers.get('content-length') === '0') {
                return { success: true };
            }

            return await res.json();

        } catch (err) {
            clearTimeout(timeoutId);

            // Timeout (AbortError gerado pelo controller)
            if (err.name === 'AbortError') {
                throw new APIError('A requisição demorou demais. Verifique sua conexão.', 408);
            }

            // Sem conexão com o servidor
            if (err instanceof TypeError && err.message.includes('fetch')) {
                throw new APIError('Sem conexão com o servidor.', 0);
            }

            // Re-lança erros que já são APIError (evita double-wrap)
            throw err;
        }
    }

    // ============================================================
    // MÉTODOS PÚBLICOS
    // ============================================================
    static async get(endpoint) {
        return this._request(endpoint);
    }

    static async post(endpoint, data) {
        return this._request(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    static async put(endpoint, data) {
        return this._request(endpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    static async delete(endpoint) {
        return this._request(endpoint, { method: 'DELETE' });
    }

    static async upload(endpoint, formData) {
        // Sem Content-Type: o browser define automaticamente com o boundary correto
        return this._request(endpoint, {
            method: 'POST',
            body: formData,
        });
    }
}

// ============================================================
// CLASSE DE ERRO CUSTOMIZADA
// ============================================================
class APIError extends Error {
    constructor(message, status = 0) {
        super(message);
        this.name = 'APIError';
        this.status = status;
    }

    /** Erro de autenticação (sessão expirada) */
    get isUnauthorized() { return this.status === 401; }

    /** Recurso não encontrado */
    get isNotFound() { return this.status === 404; }

    /** Erro de servidor */
    get isServerError() { return this.status >= 500; }

    /** Sem conexão ou timeout */
    get isNetworkError() { return this.status === 0 || this.status === 408; }
}
