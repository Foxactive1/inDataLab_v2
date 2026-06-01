// theme-system.js - Sistema completo de tema claro e escuro

class ThemeManager {
    constructor() {
        this.STORAGE_KEY = 'app-theme-preference';
        this.LIGHT_THEME = 'light';
        this.DARK_THEME = 'dark';
        this.AUTO_THEME = 'auto';
        this.init();
    }

    // ============================================================
    // INICIALIZAÇÃO
    // ============================================================
    init() {
        // Detecta tema salvo ou usa preferência do sistema
        const savedTheme = localStorage.getItem(this.STORAGE_KEY);
        const preferredTheme = savedTheme || this.AUTO_THEME;
        
        // Aplica o tema
        this.setTheme(preferredTheme);
        
        // Monitora mudança de preferência do sistema
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (localStorage.getItem(this.STORAGE_KEY) === this.AUTO_THEME || !localStorage.getItem(this.STORAGE_KEY)) {
                this.applySystemTheme();
            }
        });
    }

    // ============================================================
    // DEFINIR TEMA
    // ============================================================
    setTheme(theme) {
        localStorage.setItem(this.STORAGE_KEY, theme);
        
        if (theme === this.AUTO_THEME) {
            this.applySystemTheme();
        } else {
            this.applyTheme(theme === this.DARK_THEME);
        }
        
        this.updateThemeButton();
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
        const html = document.documentElement;
        
        if (isDark) {
            html.setAttribute('data-bs-theme', 'dark');
            document.body.classList.add('dark-theme');
            document.body.classList.remove('light-theme');
        } else {
            html.setAttribute('data-bs-theme', 'light');
            document.body.classList.add('light-theme');
            document.body.classList.remove('dark-theme');
        }
        
        // Dispara evento customizado para outros scripts
        window.dispatchEvent(new CustomEvent('themeChanged', { 
            detail: { isDark, theme: isDark ? 'dark' : 'light' } 
        }));
    }

    // ============================================================
    // ALTERNAR TEMA
    // ============================================================
    toggleTheme() {
        const currentTheme = localStorage.getItem(this.STORAGE_KEY) || this.AUTO_THEME;
        let nextTheme;
        
        if (currentTheme === this.LIGHT_THEME) {
            nextTheme = this.DARK_THEME;
        } else if (currentTheme === this.DARK_THEME) {
            nextTheme = this.AUTO_THEME;
        } else {
            // Se for AUTO, detecta o atual e inverte
            const isDarkNow = document.documentElement.getAttribute('data-bs-theme') === 'dark';
            nextTheme = isDarkNow ? this.LIGHT_THEME : this.DARK_THEME;
        }
        
        this.setTheme(nextTheme);
    }

    // ============================================================
    // ATUALIZAR BOTÃO DE TEMA
    // ============================================================
    updateThemeButton() {
        const btn = document.getElementById('themeToggleBtn');
        const icon = btn?.querySelector('i');
        const label = btn?.querySelector('.theme-label');
        
        if (!btn) return;
        
        const savedTheme = localStorage.getItem(this.STORAGE_KEY) || this.AUTO_THEME;
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        
        // Atualiza classe do botão
        btn.classList.remove('light-mode', 'dark-mode', 'auto-mode');
        btn.classList.add(savedTheme === this.AUTO_THEME ? 'auto-mode' : (isDark ? 'dark-mode' : 'light-mode'));
        
        // Atualiza ícone
        if (icon) {
            icon.className = '';
            if (savedTheme === this.AUTO_THEME) {
                icon.classList.add('bi', 'bi-circle-half');
            } else if (isDark) {
                icon.classList.add('bi', 'bi-moon-stars-fill');
            } else {
                icon.classList.add('bi', 'bi-sun-fill');
            }
        }
        
        // Atualiza label
        if (label) {
            if (savedTheme === this.AUTO_THEME) {
                label.textContent = 'Auto';
            } else if (isDark) {
                label.textContent = 'Escuro';
            } else {
                label.textContent = 'Claro';
            }
        }
    }

    // ============================================================
    // OBTER TEMA ATUAL
    // ============================================================
    getCurrentTheme() {
        return localStorage.getItem(this.STORAGE_KEY) || this.AUTO_THEME;
    }

    // ============================================================
    // VERIFICAR SE É MODO ESCURO
    // ============================================================
    isDarkMode() {
        return document.documentElement.getAttribute('data-bs-theme') === 'dark';
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
