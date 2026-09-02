/**
 * Fetches JSON files from the 'logs/' directory.
 * If deployed to Vercel, it expects 'logs/' to be served publicly.
 */

async function fetchLogData(filename) {
    try {
        const response = await fetch(`logs/${filename}`);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        console.warn(`Could not load ${filename}:`, e);
        return null;
    }
}

function formatCurrency(val) {
    if (val === null || val === undefined) return '-';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
}

function formatNumber(val, decimals = 2) {
    if (val === null || val === undefined) return '-';
    return Number(val).toFixed(decimals);
}

async function renderAccount() {
    const data = await fetchLogData('account.json');
    const container = document.getElementById('account-container');
    
    if (!data) return; // Fallback to empty state already in HTML
    
    container.innerHTML = `
        <div class="card">
            <div class="card-label">Equity</div>
            <div class="card-value">${formatCurrency(data.equity)}</div>
        </div>
        <div class="card">
            <div class="card-label">Buying Power</div>
            <div class="card-value">${formatCurrency(data.buying_power)}</div>
        </div>
        <div class="card">
            <div class="card-label">Initial Margin</div>
            <div class="card-value">${formatCurrency(data.initial_margin)}</div>
        </div>
        <div class="card">
            <div class="card-label">Open Positions</div>
            <div class="card-value">${data.positions || 0}</div>
        </div>
    `;
}

async function renderRiskDecisions() {
    const data = await fetchLogData('risk_decisions.json');
    const tbody = document.getElementById('risk-body');
    
    if (!data || !Array.isArray(data) || data.length === 0) return;
    
    tbody.innerHTML = data.map(decision => {
        const statusClass = decision.status === 'REFUSED' ? 'status-refused' : 'status-approved';
        return `
            <tr>
                <td class="mono">${decision.timestamp || '-'}</td>
                <td>${decision.action || '-'}</td>
                <td class="mono">${decision.symbol || '-'}</td>
                <td class="mono">${formatCurrency(decision.capital_at_risk)}</td>
                <td class="${statusClass}">${decision.status}</td>
                <td>${decision.reason || '-'}</td>
            </tr>
        `;
    }).join('');
}

async function renderValidation() {
    const data = await fetchLogData('validation.json');
    const tbody = document.getElementById('validation-body');
    
    if (!data || !Array.isArray(data) || data.length === 0) return;
    
    tbody.innerHTML = data.map(row => {
        const statusClass = row.result === 'FAIL' ? 'status-refused' : 'status-approved';
        return `
            <tr>
                <td class="mono">${row.strategy || '-'}</td>
                <td class="mono">${row.symbol || '-'}</td>
                <td class="mono">${row.win_rate !== undefined ? formatNumber(row.win_rate * 100, 1) + '%' : '-'}</td>
                <td class="mono">${formatNumber(row.sharpe)}</td>
                <td class="mono">${formatNumber(row.sharpe_ci_lower)}</td>
                <td class="${statusClass}">${row.result}</td>
            </tr>
        `;
    }).join('');
}

document.addEventListener('DOMContentLoaded', () => {
    renderAccount();
    renderRiskDecisions();
    renderValidation();
});
