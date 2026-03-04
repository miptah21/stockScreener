/**
 * watchlist.js — Shared Watchlist & Portfolio Manager
 * Uses localStorage for persistent client-side storage.
 * Can be included in any page for ⭐ toggle functionality.
 */

/* ─── Helpers ──────────────────────────────────────────────────────── */

/** Escape HTML to prevent XSS */
function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/** Validate a watchlist item structure */
function _validateWatchlistItem(item) {
    return item
        && typeof item.ticker === 'string'
        && item.ticker.length > 0
        && item.ticker.length <= 20;
}

/** Validate a portfolio entry structure */
function _validatePortfolioEntry(entry) {
    return entry
        && typeof entry.ticker === 'string'
        && typeof entry.id === 'string'
        && typeof entry.buyPrice === 'number' && entry.buyPrice >= 1
        && typeof entry.lots === 'number' && entry.lots > 0 && Number.isInteger(entry.lots);
}


/* ─── WatchlistManager ─────────────────────────────────────────────── */

const WatchlistManager = {
    KEY: 'finance_watchlist',

    getAll() {
        try {
            const raw = JSON.parse(localStorage.getItem(this.KEY)) || [];
            return Array.isArray(raw) ? raw.filter(_validateWatchlistItem) : [];
        } catch { return []; }
    },

    add(ticker, notes = '') {
        if (typeof ticker !== 'string' || !ticker.trim()) return false;
        const list = this.getAll();
        if (list.find(item => item.ticker === ticker)) return false;
        list.push({
            ticker: ticker.trim().substring(0, 20),
            notes: typeof notes === 'string' ? notes.substring(0, 200) : '',
            addedAt: new Date().toISOString()
        });
        localStorage.setItem(this.KEY, JSON.stringify(list));
        return true;
    },

    remove(ticker) {
        const list = this.getAll().filter(item => item.ticker !== ticker);
        localStorage.setItem(this.KEY, JSON.stringify(list));
    },

    has(ticker) {
        return this.getAll().some(item => item.ticker === ticker);
    },

    updateNotes(ticker, notes) {
        const list = this.getAll();
        const item = list.find(i => i.ticker === ticker);
        if (item) {
            item.notes = typeof notes === 'string' ? notes.substring(0, 200) : '';
            localStorage.setItem(this.KEY, JSON.stringify(list));
        }
    },

    count() { return this.getAll().length; }
};


/* ─── PortfolioManager ─────────────────────────────────────────────── */

const PortfolioManager = {
    KEY: 'finance_portfolio',

    getAll() {
        try {
            const raw = JSON.parse(localStorage.getItem(this.KEY)) || [];
            return Array.isArray(raw) ? raw.filter(_validatePortfolioEntry) : [];
        } catch { return []; }
    },

    add(entry) {
        if (!entry || typeof entry.ticker !== 'string') return null;
        const list = this.getAll();
        entry.id = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
        entry.buyPrice = Math.round(Number(entry.buyPrice) || 0);
        entry.lots = Math.max(1, Math.floor(Number(entry.lots) || 1));
        entry.addedAt = new Date().toISOString();
        list.push(entry);
        localStorage.setItem(this.KEY, JSON.stringify(list));
        return entry.id;
    },

    remove(id) {
        const list = this.getAll().filter(e => e.id !== id);
        localStorage.setItem(this.KEY, JSON.stringify(list));
    },

    update(id, data) {
        const list = this.getAll();
        const idx = list.findIndex(e => e.id === id);
        if (idx >= 0) { Object.assign(list[idx], data); localStorage.setItem(this.KEY, JSON.stringify(list)); }
    },

    count() { return this.getAll().length; },

    getTotalInvested() {
        return this.getAll().reduce((sum, e) => sum + (e.buyPrice * e.lots * 100), 0);
    },

    exportJSON() {
        return JSON.stringify({
            watchlist: WatchlistManager.getAll(),
            portfolio: this.getAll(),
            exportedAt: new Date().toISOString()
        }, null, 2);
    },

    importJSON(json) {
        try {
            const data = JSON.parse(json);
            if (data.watchlist && Array.isArray(data.watchlist)) {
                localStorage.setItem(WatchlistManager.KEY, JSON.stringify(data.watchlist.filter(_validateWatchlistItem)));
            }
            if (data.portfolio && Array.isArray(data.portfolio)) {
                localStorage.setItem(this.KEY, JSON.stringify(data.portfolio.filter(_validatePortfolioEntry)));
            }
            return true;
        } catch { return false; }
    }
};


/* ─── Star Toggle (for other pages) ────────────────────────────────── */

function toggleWatchlistStar(ticker, btn) {
    if (WatchlistManager.has(ticker)) {
        WatchlistManager.remove(ticker);
        if (btn) { btn.textContent = '☆'; btn.title = 'Tambah ke Watchlist'; btn.classList.remove('starred'); }
    } else {
        WatchlistManager.add(ticker);
        if (btn) { btn.textContent = '★'; btn.title = 'Hapus dari Watchlist'; btn.classList.add('starred'); }
    }
}
