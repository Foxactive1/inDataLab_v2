/**
 * utils.js — Funções utilitárias para o InDataLab
 */

/**
 * Escapa caracteres HTML perigosos para evitar XSS
 * @param {string} str - String a ser escapada
 * @returns {string}
 */
function escapeHtml(str) {
    if (!str) return '';
    const entityMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };
    return String(str).replace(/[&<>"']/g, match => entityMap[match]);
}

/**
 * Debounce — atrasa a execução de uma função
 * @param {Function} fn - Função a ser executada
 * @param {number} delay - Tempo em milissegundos
 * @returns {Function}
 */
function debounce(fn, delay = 300) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Formata uma data ISO para exibição amigável
 * @param {string} isoString - Data no formato ISO
 * @returns {string}
 */
function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Trunca texto longo com reticências
 * @param {string} text - Texto original
 * @param {number} maxLength - Comprimento máximo
 * @returns {string}
 */
function truncate(text, maxLength = 60) {
    if (!text || text.length <= maxLength) return text || '';
    return text.slice(0, maxLength).trimEnd() + '…';
}

/**
 * Gera um ID único simples (para uso local)
 * @returns {string}
 */
function generateUID() {
    return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

/**
 * Copia texto para a área de transferência
 * @param {string} text - Texto a ser copiado
 * @returns {Promise<boolean>}
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        console.error('Falha ao copiar:', err);
        return false;
    }
}

/**
 * Detecta se o dispositivo é mobile (largura < 992px)
 * @returns {boolean}
 */
function isMobile() {
    return window.innerWidth < 992;
}

/**
 * Converte bytes para formato legível
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

/**
 * Sanitiza nome de arquivo (remove caracteres inválidos)
 * @param {string} name - Nome original
 * @returns {string}
 */
function sanitizeFileName(name) {
    return name.replace(/[^a-zA-Z0-9._-]/g, '_').substring(0, 100);
}

/**
 * Detecta o tipo de arquivo a partir da extensão
 * @param {string} filename
 * @returns {string} - 'csv', 'excel', 'json', 'sqlite', 'unknown'
 */
function detectFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const map = {
        'csv': 'csv',
        'txt': 'csv',
        'xlsx': 'excel',
        'xls': 'excel',
        'json': 'json',
        'db': 'sqlite',
        'sqlite': 'sqlite',
        'sqlite3': 'sqlite'
    };
    return map[ext] || 'unknown';
}

// Disponibilizar globalmente se necessário (para uso em script inline)
window.escapeHtml = escapeHtml;
window.debounce = debounce;
window.formatDate = formatDate;
window.truncate = truncate;
window.copyToClipboard = copyToClipboard;
window.isMobile = isMobile;
window.formatFileSize = formatFileSize;
window.detectFileType = detectFileType;