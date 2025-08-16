const root = typeof window !== 'undefined' ? window : globalThis;

(function () {
    if (typeof localStorage === 'undefined') return;
    const theme = localStorage.getItem('setting_theme') || 'seeker';
    setTheme(theme);
})();

function setTheme(theme) {
    const html = document.documentElement;
    html.classList.remove('theme-seeker', 'theme-dark', 'theme-light');
    html.classList.add(`theme-${theme}`);
    const disable = localStorage.getItem('setting_disableAnimation') === 'true';
    if (theme === 'seeker' && !disable) {
        html.classList.remove('no-anim');
    } else {
        html.classList.add('no-anim');
    }
    localStorage.setItem('setting_theme', theme);
}

root.setTheme = setTheme;

function formatSol(amount, price) {
    const usd = amount * price;
    const sign = amount < 0 ? '-' : '';
    return `${sign}${Math.abs(amount).toFixed(2)} SOL (${sign}$${Math.abs(usd).toFixed(2)})`;
}

function formatSolChange(amount, price) {
    const usd = amount * price;
    const sign = amount >= 0 ? '+' : '-';
    return `${sign}${Math.abs(amount).toFixed(2)} SOL (${sign}$${Math.abs(usd).toFixed(2)})`;
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '-';
    return `${sign}${Math.abs(value).toFixed(2)}%`;
}

root.formatSol = formatSol;
root.formatSolChange = formatSolChange;
root.formatPercent = formatPercent;

if (typeof module !== 'undefined') {
    module.exports = { formatSol, formatSolChange, formatPercent };
}

