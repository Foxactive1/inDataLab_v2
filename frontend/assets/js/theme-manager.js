// theme-manager.js - Sistema reformulado de tema para InDataLab

class ThemeManager {
    constructor() {
        this.STORAGE_KEY = 'indatalab-theme-preference';
        this.LIGHT_THEME = 'light';
        this.DARK_THEME = 'dark';
        this.SYSTEM_THEME = 'system';
        this.DEFAULT_THEME = this.SYSTEM_THEME;
        this.init();
    }

    // ============================================================
    // INICIALIZAÇÃO
    // ============================================================
    init() {
        const savedTheme = localStorage.getItem(this.STORAGE_KEY) || this.DEFAULT_THEME;
        this.setTheme(savedTheme);
        
        // Monitora mudança de preferência do sistema
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (this.getCurrentTheme() === this.SYSTEM_THEME) {
                this.applySystemTheme();
                this.updateButton();
            }
        });
    }

    // ============================================================
    // DEFINIR TEMA
    // ============================================================
    setTheme(theme) {
        localStorage.setItem(this.STORAGE_KEY, theme);
        
        if (theme === this.SYSTEM_THEME) {
            this.applySystemTheme();
        } else {
            this.applyTheme(theme === this.DARK_THEME);
        }
        
        this.updateButton();
        this.dispatchEvent(theme);
    }

    // ============================================================
    // APLICAR TEMA DO SISTEMA
    // ============================================================
    applySystemTheme() {
        const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
        this.applyTheme(isDarkMode);
    }

    // ============================================================
    // APLICAR TEMA (Light/Dark)
    // ============================================================
    applyTheme(isDark) {
        const htmlElement = document.documentElement;
        
        if (isDark) {
            htmlElement.setAttribute('data-theme', 'dark');
        } else {
            htmlElement.removeAttribute('data-theme');
        }
        
        // Força atualização do Bootstrap
        if (isDark) {
            htmlElement.setAttribute('data-bs-theme', 'dark');
        } else {
            htmlElement.removeAttribute('data-bs-theme');
        }
    }

    // ============================================================
    // ALTERNAR TEMA (Cicla entre Claro → Escuro → Sistema)
    // ============================================================
    toggleTheme() {
        const currentTheme = this.getCurrentTheme();
        let nextTheme;
        
        if (currentTheme === this.LIGHT_THEME) {
            nextTheme = this.DARK_THEME;
        } else if (currentTheme === this.DARK_THEME) {
            nextTheme = this.SYSTEM_THEME;
        } else {
            // Se for SISTEMA, detecta o atual e inverte
            const isDarkNow = this.isDarkMode();
            nextTheme = isDarkNow ? this.LIGHT_THEME : this.DARK_THEME;
        }
        
        this.setTheme(nextTheme);
    }

    // ============================================================
    // ATUALIZAR VISUAL DO BOTÃO
    // ============================================================
    updateButton() {
        const btn = document.getElementById('themeToggleBtn');
        if (!btn) return;
        
        const currentTheme = this.getCurrentTheme();
        const isDark = this.isDarkMode();
        
        // Encontra ícone e label dentro do botão
        const icon = btn.querySelector('i');
        const label = btn.querySelector('.theme-label');
        
        // Remove todas as classes
        btn.className = 'btn-action';
        
        // Atualiza ícone e label
        if (icon) {
            icon.className = '';
            if (currentTheme === this.SYSTEM_THEME) {
                icon.classList.add('bi', 'bi-circle-half');
            } else if (isDark) {
                icon.classList.add('bi', 'bi-moon-stars-fill');
            } else {
                icon.classList.add('bi', 'bi-sun-fill');
            }
        }
        
        if (label) {
            if (currentTheme === this.SYSTEM_THEME) {
                label.textContent = 'Auto';
            } else if (isDark) {
                label.textContent = 'Escuro';
            } else {
                label.textContent = 'Claro';
            }
        }
    }

    // ============================================================
    // VERIFICAR MODO ESCURO
    // ============================================================
    isDarkMode() {
        return document.documentElement.getAttribute('data-theme') === 'dark';
    }

    // ============================================================
    // OBTER TEMA ATUAL
    // ============================================================
    getCurrentTheme() {
        return localStorage.getItem(this.STORAGE_KEY) || this.DEFAULT_THEME;
    }

    // ============================================================
    // DISPARAR EVENTO CUSTOMIZADO
    // ============================================================
    dispatchEvent(theme) {
        const isDark = this.isDarkMode();
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: {
                theme: theme,
                isDark: isDark,
                actualTheme: isDark ? 'dark' : 'light'
            }
        }));
    }
}

// Inicializar quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.themeManager = new ThemeManager();
    });
} else {
    window.themeManager = new ThemeManager();
}
