function formatSol(amount, price) {
    const usd = amount * price;
    return `${amount.toFixed(2)} SOL ($${usd.toFixed(2)})`;
}

function formatSolChange(amount, price) {
    const usd = amount * price;
    const sign = amount >= 0 ? '+' : '-';
    return `${sign}${Math.abs(amount).toFixed(2)} SOL ($${Math.abs(usd).toFixed(2)})`;
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '-';
    return `${sign}${Math.abs(value).toFixed(2)}%`;
}

const root = typeof window !== 'undefined' ? window : globalThis;
root.formatSol = formatSol;
root.formatSolChange = formatSolChange;
root.formatPercent = formatPercent;

if (typeof module !== 'undefined') {
    module.exports = { formatSol, formatSolChange, formatPercent };
}

