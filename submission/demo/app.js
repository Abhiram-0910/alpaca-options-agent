/**
 * Fetches JSON files from the 'data/' directory.
 * If deployed to Vercel, it expects 'data/' to be served publicly.
 */

async function fetchDashboardData() {
    try {
        const response = await fetch(`data/dashboard.json`);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        console.warn(`Could not load dashboard.json:`, e);
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

function renderAccount(account) {
    const container = document.getElementById('account-container');
    
    if (!account || account.error) {
        container.innerHTML = `<div class="empty-state">${account?.error || 'No account data available.'}</div>`;
        return;
    }
    
    container.innerHTML = `
        <div class="card">
            <div class="card-label">Equity</div>
            <div class="card-value">${formatCurrency(account.equity)}</div>
        </div>
        <div class="card">
            <div class="card-label">Buying Power</div>
            <div class="card-value">${formatCurrency(account.buying_power)}</div>
        </div>
        <div class="card">
            <div class="card-label">Options BP</div>
            <div class="card-value">${formatCurrency(account.options_buying_power)}</div>
        </div>
        <div class="card">
            <div class="card-label">Open Positions</div>
            <div class="card-value">${account.open_position_count !== null ? account.open_position_count : 0}</div>
        </div>
    `;
}

function renderRiskDecisions(decisions) {
    const tbody = document.getElementById('risk-body');
    const readDesc = document.getElementById('read-tool-desc');
    
    if (!decisions || !Array.isArray(decisions) || decisions.length === 0) return;
    
    const orderDecisions = decisions.filter(d => d.tool === 'place_option_order' || d.tool === 'place_stock_order');
    const readCount = decisions.length - orderDecisions.length;
    
    if (readDesc) {
        readDesc.textContent = `Filtered ${readCount} read-only market data requests. Displaying order execution decisions only.`;
    }
    
    if (orderDecisions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No order decisions recorded yet.</td></tr>';
        return;
    }
    
    tbody.innerHTML = orderDecisions.map(decision => {
        const statusClass = !decision.approved ? 'status-refused' : 'status-approved';
        const statusText = decision.approved ? 'APPROVED' : 'REFUSED';
        return `
            <tr>
                <td class="mono">${decision.ts ? new Date(decision.ts).toLocaleTimeString() : '-'}</td>
                <td>${decision.tool || '-'}</td>
                <td class="mono">${decision.symbol || '-'}</td>
                <td class="mono">${decision.estimated_capital_at_risk !== null ? formatCurrency(decision.estimated_capital_at_risk) : 'N/A'}</td>
                <td class="${statusClass}">${statusText}</td>
                <td>${decision.reason || '-'}</td>
            </tr>
        `;
    }).join('');
}

function renderValidation(meta, validationData) {
    const tbody = document.getElementById('validation-body');
    const badge = document.getElementById('validation-badge');
    const desc = document.getElementById('validation-desc');

    if (meta) {
        const refusedCount = meta.distinct_pairs_evaluated - meta.pairs_cleared;
        badge.textContent = `${refusedCount} of ${meta.distinct_pairs_evaluated} Candidates Refused`;
        
        let extraLine = '';
        if (meta.pairs_cleared === 0 && meta.pairs_passing_primary_gate > 0) {
            extraLine = ` However, ${meta.pairs_passing_primary_gate} pair passed the bootstrap CI gate but failed sub-period stability checks, proving the gate catches unstable edge.`;
        }
        
        desc.textContent = `Evaluated ${meta.total_validation_records} total validation records (including extended-history and sub-period re-runs). The statistical validation gate refused ${refusedCount} distinct pairs.${extraLine}`;
    }

    if (!validationData || !Array.isArray(validationData) || validationData.length === 0) return;
    
    tbody.innerHTML = validationData.map(row => {
        const statusClass = !row.passed ? 'status-refused' : 'status-approved';
        const resultText = row.passed ? 'PASS' : 'FAIL';
        return `
            <tr>
                <td class="mono">${row.strategy || '-'}</td>
                <td class="mono">${row.symbol || '-'}</td>
                <td class="mono">${row.win_rate !== null ? formatNumber(row.win_rate * 100, 1) + '%' : '-'}</td>
                <td class="mono">${formatNumber(row.sharpe)}</td>
                <td class="mono">${row.scope || '-'}</td>
                <td class="${statusClass}">${resultText}</td>
            </tr>
        `;
    }).join('');
}

function renderFooter(meta, trades) {
    const footerText = document.getElementById('footer-text');
    let hasDemoTrade = false;

    if (trades && trades.length > 0) {
        hasDemoTrade = trades.some(t => t.validation_status === 'UNVALIDATED_DEMONSTRATION');
    } else if (meta && meta.pairs_cleared === 0) {
        // Fallback if trades isn't populated but we know nothing cleared.
        hasDemoTrade = true;
    }

    if (hasDemoTrade) {
        footerText.innerHTML = `<p>UNVALIDATED_DEMONSTRATION mode active. Agent executed strictly for logic demonstration.</p>`;
    } else {
        footerText.innerHTML = `<p>Alpaca Agent - Validated mode active.</p>`;
    }
}

function renderDeterminism(determinism) {
    const badge = document.getElementById('determinism-badge');
    const desc = document.getElementById('determinism-desc');
    const summary = document.getElementById('determinism-summary');
    const tableContainer = document.getElementById('determinism-table-container');
    const tbody = document.getElementById('determinism-body');

    if (!determinism || typeof determinism !== 'object') {
        if (badge) badge.textContent = 'No data';
        if (desc) desc.textContent = 'Determinism replay data will appear once the agent runs the measurement suite.';
        return;
    }

    const total = determinism.total_replays ?? 0;
    const diverged = determinism.diverged_count ?? 0;
    const toolChanged = determinism.tool_changed_count ?? 0;
    const divergenceRate = total > 0 ? ((diverged / total) * 100).toFixed(1) : '—';

    if (badge) {
        badge.textContent = `${diverged}/${total} Replays Diverged`;
        badge.className = diverged > 0 ? 'badge danger' : 'badge';
    }

    if (desc) {
        desc.textContent = `At temperature 0, fixed seed, unchanged system_fingerprint: ${diverged} of ${total} replays diverged (${divergenceRate}%). `
            + `Of those, ${toolChanged} changed the tool called — not just arguments. `
            + `One flipped from reading a chain to attempting an order. This is why authority sits in deterministic Python.`;
    }

    if (summary) {
        summary.innerHTML = `
            <div class="card">
                <div class="card-label">Replays Run</div>
                <div class="card-value">${total}</div>
            </div>
            <div class="card">
                <div class="card-label">Diverged</div>
                <div class="card-value" style="color: ${diverged > 0 ? 'var(--accent-red)' : 'var(--accent-green)'}">${diverged}</div>
            </div>
            <div class="card">
                <div class="card-label">Tool Changed (not just args)</div>
                <div class="card-value" style="color: ${toolChanged > 0 ? 'var(--accent-red)' : 'var(--accent-green)'}">${toolChanged}</div>
            </div>
            <div class="card">
                <div class="card-label">Divergence Rate</div>
                <div class="card-value">${divergenceRate}%</div>
            </div>
        `;
    }

    const replays = determinism.replays;
    if (Array.isArray(replays) && replays.length > 0 && tableContainer && tbody) {
        tableContainer.style.display = '';
        tbody.innerHTML = replays.map((r, i) => {
            const divClass = r.diverged ? 'diverged-yes' : 'diverged-no';
            const divText = r.diverged ? '✗ YES' : '✓ no';
            const toolChangedText = r.tool_changed ? '⚠ YES' : '—';
            return `
                <tr>
                    <td class="mono">${i + 1}</td>
                    <td class="${divClass}">${divText}</td>
                    <td class="mono">${r.original_tool || '—'}</td>
                    <td class="mono">${r.replayed_tool || '—'}</td>
                    <td>${r.args_changed ? '✗ changed' : '—'}</td>
                    <td style="color: ${r.tool_changed ? 'var(--accent-red)' : 'inherit'}">${toolChangedText}</td>
                </tr>
            `;
        }).join('');
    }
}

function renderAdversarial(adversarial) {
    const tbody = document.getElementById('adversarial-body');
    const badge = document.getElementById('adversarial-badge');
    const desc = document.getElementById('adversarial-desc');

    if (!adversarial || !Array.isArray(adversarial) || adversarial.length === 0) {
        if (badge) badge.textContent = 'No data';
        if (desc) desc.textContent = 'Adversarial harness data will appear once the agent runs the attack suite.';
        return;
    }

    const blocked = adversarial.filter(a => a.blocked === true).length;
    const total = adversarial.length;

    if (badge) {
        badge.textContent = `${blocked}/${total} Attacks Blocked`;
        badge.className = blocked === total ? 'badge danger' : 'badge warning';
    }
    if (desc) {
        desc.textContent = `The risk gate blocked ${blocked} of ${total} adversarial probes. Every attack, its payload, and the exact rejection reason is listed below.`;
    }

    tbody.innerHTML = adversarial.map(attack => {
        const blocked = attack.blocked === true;
        const resultClass = blocked ? 'status-pass' : 'status-fail';
        const resultText = blocked ? '✓ BLOCKED' : '✗ PASSED';
        // Show expected vs actual stopping layer
        const expectedStop = attack.expected_stop || '-';
        const actualStop = attack.actual_stop || (blocked ? '(stopped)' : '(leaked)');
        return `
            <tr>
                <td class="mono">${attack.attack_type || '-'}</td>
                <td class="payload-cell" title="${(attack.payload || '').replace(/"/g, '&quot;')}">${attack.payload || '-'}</td>
                <td class="mono">${expectedStop}</td>
                <td class="mono">${actualStop}</td>
                <td style="max-width:300px; font-size:0.8rem; color: var(--text-secondary)">${attack.rejection_reason || (blocked ? '(blocked before reaching gate)' : 'Not rejected')}</td>
                <td class="${resultClass}">${resultText}</td>
            </tr>
        `;
    }).join('');
}

function renderFillAnalysis(fillAnalysis) {
    const tbody = document.getElementById('fill-body');
    const badge = document.getElementById('fill-badge');

    if (!fillAnalysis || !Array.isArray(fillAnalysis) || fillAnalysis.length === 0) {
        if (badge) badge.textContent = 'No fills yet';
        return;
    }

    if (badge) badge.textContent = `${fillAnalysis.length} leg(s)`;

    tbody.innerHTML = fillAnalysis.map(fill => {
        const delta = fill.fill_price !== null && fill.pre_order_quote !== null
            ? (fill.fill_price - fill.pre_order_quote)
            : null;
        let deltaClass = 'fill-delta-zero';
        let deltaText = '-';
        if (delta !== null) {
            deltaText = (delta >= 0 ? '+' : '') + delta.toFixed(4);
            deltaClass = delta < 0 ? 'fill-delta-neg' : (delta > 0 ? 'fill-delta-pos' : 'fill-delta-zero');
        }
        return `
            <tr>
                <td class="mono">${fill.ts ? new Date(fill.ts).toLocaleTimeString() : '-'}</td>
                <td class="mono">${fill.order_symbol || '-'}</td>
                <td class="mono" style="font-size:0.75rem">${fill.leg_symbol || '-'}</td>
                <td class="mono">${fill.side || '-'}</td>
                <td class="mono">${fill.pre_order_quote !== null ? formatNumber(fill.pre_order_quote, 4) : '-'}</td>
                <td class="mono">${fill.fill_price !== null ? formatNumber(fill.fill_price, 4) : '-'}</td>
                <td class="${deltaClass}">${deltaText}</td>
            </tr>
        `;
    }).join('');
}

document.addEventListener('DOMContentLoaded', async () => {
    const data = await fetchDashboardData();
    if (data) {
        renderAccount(data.account);
        renderDeterminism(data.determinism);
        renderRiskDecisions(data.gate_decisions);
        renderValidation(data.meta, data.validation);
        renderAdversarial(data.adversarial);
        renderFillAnalysis(data.fill_analysis);
        renderFooter(data.meta, data.trades);
    }
});
