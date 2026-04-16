/* ── AI Consult — Portfolio Edition ────────────────────────────────────────── */

// API paths are prefixed for the portfolio site
const API_BASE = '/ai-consult';

const LOADING_STEPS = [
  { pct: 8,  text: "Connecting to market data..." },
  { pct: 20, text: "Pulling revenue, margins, cash flow..." },
  { pct: 38, text: "Running DCF valuation model..." },
  { pct: 55, text: "Comparing to sector peers..." },
  { pct: 68, text: "Flagging key risks..." },
  { pct: 78, text: "Writing institutional report..." },
  { pct: 88, text: "Translating to plain English..." },
  { pct: 95, text: "Almost there..." },
];

let loadingInterval = null;
let loadingStepIdx  = 0;
const sectionState  = { what: true, buy: true, catch: true };
let _keyAuthEnabled = false;

// ── Cursor ─────────────────────────────────────────────────────────────────────
(function initCursor() {
  const dot  = document.getElementById('cursor-dot');
  const ring = document.getElementById('cursor-ring');
  if (!dot || !ring) return;

  let mx = 0, my = 0, rx = 0, ry = 0;
  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });

  function animate() {
    rx += (mx - rx) * 0.12;
    ry += (my - ry) * 0.12;
    dot.style.left  = mx + 'px'; dot.style.top  = my + 'px';
    ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
    requestAnimationFrame(animate);
  }
  animate();

  document.querySelectorAll('a,button,input,.quick-btn,.dd-tab').forEach(el => {
    el.addEventListener('mouseenter', () => ring.style.width = ring.style.height = '52px');
    el.addEventListener('mouseleave', () => ring.style.width = ring.style.height = '32px');
  });
})();

// ── Init: check config & validate stored key ───────────────────────────────────
(async function init() {
  try {
    const res = await fetch(`${API_BASE}/config`);
    const cfg = await res.json();
    _keyAuthEnabled = !!cfg.key_auth_enabled;

    if (_keyAuthEnabled) {
      const stored = localStorage.getItem('acAccessKey');
      if (stored) {
        const info = await checkKeyInfo(stored);
        if (info.valid) {
          updateKeyBadge(info.uses_remaining, info.uses_total);
        } else {
          localStorage.removeItem('acAccessKey');
          openKeyModal();
        }
      } else {
        openKeyModal();
      }
    }
  } catch (e) { /* server unreachable on init */ }
})();

async function checkKeyInfo(key) {
  try {
    const res = await fetch(`${API_BASE}/key-info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key }),
    });
    return await res.json();
  } catch (e) { return { valid: false }; }
}

// ── Key badge ──────────────────────────────────────────────────────────────────
function updateKeyBadge(remaining, total) {
  const badge = document.getElementById('keyBadge');
  const text  = document.getElementById('keyBadgeText');
  if (!badge) return;
  badge.classList.remove('hidden', 'exhausted');
  if (remaining <= 0) {
    badge.classList.add('exhausted');
    text.textContent = 'No searches left';
  } else {
    text.textContent = `${remaining} search${remaining === 1 ? '' : 'es'} left`;
  }
}

// ── Key modal ──────────────────────────────────────────────────────────────────
function openKeyModal() {
  document.getElementById('keyModal').classList.remove('hidden');
  const stored = localStorage.getItem('acAccessKey');
  if (stored) document.getElementById('keyInput').value = stored;
  setTimeout(() => document.getElementById('keyInput').focus(), 120);
}
function closeKeyModal() {
  document.getElementById('keyModal').classList.add('hidden');
  clearKeyError();
}
function closeKeyOutside(e) {
  if (e.target.id === 'keyModal') closeKeyModal();
}
function clearKeyError() {
  const el = document.getElementById('keyError');
  el.textContent = ''; el.classList.add('hidden');
  document.getElementById('keyInput').classList.remove('error');
}
function showKeyError(msg) {
  const el = document.getElementById('keyError');
  el.textContent = msg; el.classList.remove('hidden');
  document.getElementById('keyInput').classList.add('error');
}

async function submitKey() {
  const input = document.getElementById('keyInput');
  const key   = input.value.trim().toUpperCase();
  clearKeyError();
  if (!key) { showKeyError('Please enter your access key.'); return; }

  const btn = document.getElementById('activateKeyBtn');
  btn.disabled = true; btn.textContent = 'Checking…';

  const info = await checkKeyInfo(key);
  btn.disabled = false; btn.textContent = 'Activate Key →';

  if (!info.valid) { showKeyError(info.error || 'Invalid key. Please try again.'); return; }
  if (info.uses_remaining <= 0) { showKeyError('This key has no searches left.'); return; }

  localStorage.setItem('acAccessKey', key);
  updateKeyBadge(info.uses_remaining, info.uses_total);
  closeKeyModal();
}

document.addEventListener('keydown', e => {
  const km = document.getElementById('keyModal');
  if (!km.classList.contains('hidden') && e.key === 'Enter') submitKey();
});

// ── Input handling ────────────────────────────────────────────────────────────
document.getElementById('tickerInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') handleAnalyze();
});
document.getElementById('tickerInput').addEventListener('input', e => {
  e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9.\-]/g, '');
});
document.getElementById('keyInput').addEventListener('input', e => {
  e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9\-]/g, '');
  clearKeyError();
});

function quickPick(ticker) {
  document.getElementById('tickerInput').value = ticker;
  handleAnalyze();
}

async function handleAnalyze() {
  const input  = document.getElementById('tickerInput');
  const ticker = input.value.trim().toUpperCase();

  if (!ticker) {
    input.focus(); input.style.borderColor = 'var(--red)';
    setTimeout(() => { input.style.borderColor = ''; }, 1200);
    return;
  }
  if (!/^[A-Z0-9.\-]{1,10}$/.test(ticker)) {
    showError(`"${ticker}" doesn't look like a valid ticker. Try AAPL, TSLA, BNS.`);
    return;
  }

  if (_keyAuthEnabled) {
    const key = localStorage.getItem('acAccessKey');
    if (!key) { openKeyModal(); return; }
  }

  showLoading(ticker);

  try {
    const key     = localStorage.getItem('acAccessKey') || '';
    const payload = _keyAuthEnabled ? { ticker, key } : { ticker };

    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    stopLoading();

    if (_keyAuthEnabled && typeof data.uses_remaining === 'number') {
      updateKeyBadge(data.uses_remaining, Number(localStorage.getItem('acAccessKeyTotal') || 3));
    }

    if (!response.ok || data.error) {
      if (data.key_required) {
        localStorage.removeItem('acAccessKey');
        openKeyModal();
        return;
      }
      showError(data.error || 'Analysis failed. Please try again.');
      return;
    }

    try {
      displayResults(data);
    } catch (displayErr) {
      console.error('Display error:', displayErr);
      showError('Failed to display results. Please try again.');
    }

  } catch (err) {
    stopLoading();
    showError('Network error. Make sure the server is running and try again.');
  }
}

// ── Loading ────────────────────────────────────────────────────────────────────
function showLoading(ticker) {
  showSection('loadingSection');
  setProgressBar(0);
  document.getElementById('loadingTitle').textContent = `Analysing ${ticker}...`;
  document.getElementById('loadingSteps').textContent = LOADING_STEPS[0].text;
  loadingStepIdx = 0;
  loadingInterval = setInterval(() => {
    loadingStepIdx = Math.min(loadingStepIdx + 1, LOADING_STEPS.length - 1);
    const step = LOADING_STEPS[loadingStepIdx];
    setProgressBar(step.pct);
    document.getElementById('loadingSteps').textContent = step.text;
  }, 1500);
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Analysing...';
}
function stopLoading() {
  clearInterval(loadingInterval);
  setProgressBar(100);
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = false;
  btn.querySelector('.btn-text').textContent = 'Analyse';
}
function setProgressBar(pct) {
  document.getElementById('progressBar').style.width = pct + '%';
}

// ── Error ──────────────────────────────────────────────────────────────────────
function showError(msg) {
  document.getElementById('errorMessage').textContent = msg;
  showSection('errorSection');
}

// ── Results ────────────────────────────────────────────────────────────────────
function displayResults(data) {
  const { ticker, name, sector, current_price, fair_value, bull_value, bear_value,
          verdict, sections, financials_snapshot,
          composite_fair_value, analyst_target } = data;

  const headline_fv = composite_fair_value || fair_value;

  document.getElementById('resTicker').textContent = ticker;
  document.getElementById('resName').textContent   = name || ticker;
  document.getElementById('resSector').textContent = sector || '';
  document.getElementById('resPrice').textContent  = fmtPrice(current_price);
  document.getElementById('resFairValue').textContent = headline_fv ? fmtPrice(headline_fv) : '—';
  document.getElementById('resAnalystTarget').textContent =
    financials_snapshot?.analyst_target ? fmtPrice(financials_snapshot.analyst_target) : '—';
  document.getElementById('resCompsEstimate').textContent = '…';
  _loadCompsEstimate();

  const verdictMap = {
    'UNDERPRICED':       { emoji: '🟢', word: 'UNDERPRICED',  caption: 'Stock appears to trade below estimated fair value', cls: 'verdict-buy' },
    'FAIRLY PRICED':     { emoji: '🟨', word: 'FAIRLY PRICED', caption: 'Stock appears to trade near estimated fair value',  cls: 'verdict-hold' },
    'OVERPRICED':        { emoji: '🔴', word: 'OVERPRICED',   caption: 'Stock appears to trade above estimated fair value', cls: 'verdict-skip' },
    'INSUFFICIENT_DATA': { emoji: '🟨', word: 'FAIRLY PRICED', caption: 'Not enough data for a confident estimate',          cls: 'verdict-hold' },
  };
  const v = verdictMap[verdict] || verdictMap['FAIRLY PRICED'];
  const banner = document.getElementById('verdictBanner');
  banner.className = `verdict-banner ${v.cls}`;
  document.getElementById('verdictEmoji').textContent  = v.emoji;
  document.getElementById('verdictWord').textContent   = v.word;

  if (current_price && headline_fv) {
    const ratio = current_price / headline_fv;
    let caption = v.caption;
    if (ratio < 0.90) caption = `${pct((headline_fv - current_price) / headline_fv)} below AI fair value`;
    else if (ratio > 1.15) caption = `${pct((current_price - headline_fv) / headline_fv)} above AI fair value`;
    else caption = `Within ${pct(Math.abs(ratio - 1))} of AI fair value`;
    document.getElementById('verdictCaption').textContent = caption;
  } else {
    document.getElementById('verdictCaption').textContent = v.caption;
  }

  document.getElementById('bullVal').textContent = bull_value  ? fmtPrice(bull_value)  : '—';
  document.getElementById('baseVal').textContent = headline_fv ? fmtPrice(headline_fv) : '—';
  document.getElementById('bearVal').textContent = bear_value  ? fmtPrice(bear_value)  : '—';

  if (sections) {
    document.getElementById('text-what').textContent = sections.what || '';
    document.getElementById('text-buy').textContent  = sections.should_buy || '';
    const catchEl = document.getElementById('text-catch');
    if (sections.catch) catchEl.innerHTML = formatRisks(sections.catch);
  }

  if (financials_snapshot) {
    const s = financials_snapshot;
    document.getElementById('stat-pe').textContent     = s.pe_ratio      ? `${s.pe_ratio.toFixed(1)}x`  : '—';
    document.getElementById('stat-rev').textContent    = s.revenue_growth ? pct(s.revenue_growth)        : '—';
    document.getElementById('stat-margin').textContent = s.profit_margin  ? pct(s.profit_margin)         : '—';
    document.getElementById('stat-beta').textContent   = s.beta           ? s.beta.toFixed(2)            : '—';
    document.getElementById('stat-target').textContent = s.analyst_target ? fmtPrice(s.analyst_target)   : '—';
  }

  _cachedCompsData = null;
  populateDeepDive(data);

  document.getElementById('deepDivePanel').classList.add('hidden');
  document.getElementById('deepDiveBtnText').textContent = 'View Full Analysis';
  document.getElementById('deepDiveChevron').classList.remove('rotated');
  switchTab('dcf');

  ['what', 'buy', 'catch'].forEach(id => {
    sectionState[id] = true;
    const body    = document.getElementById(`body-${id}`);
    const chevron = document.getElementById(`chevron-${id}`);
    body.classList.remove('collapsed');
    body.style.maxHeight = body.scrollHeight + 'px';
    chevron.classList.remove('rotated');
  });

  document.querySelectorAll('.analysis-card').forEach(card => card.classList.add('fade-in'));
  showSection('resultsSection');
  setTimeout(() => {
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 50);
}

// ── Markdown renderer ──────────────────────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return '';
  const lines = text.split('\n');
  let html = '', inList = false;
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    if (/^---+$/.test(line.trim())) {
      if (inList) { html += '</ul>'; inList = false; }
      html += '<hr class="report-hr">'; continue;
    }
    if (/^##\s/.test(line)) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h3 class="report-h3">${renderInline(line.replace(/^##\s+/, ''))}</h3>`; continue;
    }
    if (/^[•\-]\s/.test(line.trim())) {
      if (!inList) { html += '<ul class="report-ul">'; inList = true; }
      html += `<li>${renderInline(line.replace(/^[•\-]\s/, ''))}</li>`; continue;
    }
    if (/^\d+\.\s/.test(line.trim())) {
      if (!inList) { html += '<ul class="report-ul">'; inList = true; }
      html += `<li>${renderInline(line.replace(/^\d+\.\s/, ''))}</li>`; continue;
    }
    if (!line.trim()) {
      if (inList) { html += '</ul>'; inList = false; }
      continue;
    }
    if (inList) { html += '</ul>'; inList = false; }
    html += `<p class="report-p">${renderInline(line)}</p>`;
  }
  if (inList) html += '</ul>';
  return html;
}
function renderInline(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,   '<em>$1</em>')
    .replace(/`(.+?)`/g,     '<code>$1</code>');
}

// ── Risk card renderer ─────────────────────────────────────────────────────────
function formatRisks(text) {
  if (!text) return '';
  const bulletPattern = /^[•\-]\s*\*\*([^*]+)\*\*\s*[—\-–]\s*(.+)$/gm;
  let blocks = [], match;
  while ((match = bulletPattern.exec(text)) !== null) {
    blocks.push({ title: match[1].trim(), body: match[2].trim() });
  }
  if (blocks.length === 0) {
    const blockPattern = /\*\*([^*]+)\*\*\s*\n([\s\S]*?)(?=\n\*\*|$)/g;
    while ((match = blockPattern.exec(text)) !== null) {
      const body = match[2].trim();
      if (body) blocks.push({ title: match[1].trim(), body });
    }
  }
  if (blocks.length > 0) {
    return blocks.map(b => `
      <div class="risk-block">
        <div class="risk-title">${escapeHtml(b.title)}</div>
        <p class="risk-body">${escapeHtml(b.body)}</p>
      </div>`).join('');
  }
  return formatBullets(text);
}
function formatBullets(text) {
  const lines = text.split('\n').filter(l => l.trim());
  const bullets = lines.filter(l => l.trim().startsWith('•') || l.trim().startsWith('-'));
  if (bullets.length > 0) {
    const items = bullets.map(l => `<li>${escapeHtml(l.replace(/^[•\-]\s*/, '').trim())}</li>`).join('');
    return `<ul>${items}</ul>`;
  }
  return `<p>${escapeHtml(text)}</p>`;
}
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Card toggle ────────────────────────────────────────────────────────────────
function toggleCard(id) {
  sectionState[id] = !sectionState[id];
  const body    = document.getElementById(`body-${id}`);
  const chevron = document.getElementById(`chevron-${id}`);
  if (sectionState[id]) {
    body.style.maxHeight = body.scrollHeight + 'px';
    body.classList.remove('collapsed');
    chevron.classList.remove('rotated');
  } else {
    body.style.maxHeight = body.scrollHeight + 'px';
    requestAnimationFrame(() => {
      body.style.maxHeight = body.scrollHeight + 'px';
      requestAnimationFrame(() => {
        body.style.maxHeight = '0';
        body.classList.add('collapsed');
        chevron.classList.add('rotated');
      });
    });
  }
}

// ── Section visibility ─────────────────────────────────────────────────────────
function showSection(id) {
  ['hero', 'loadingSection', 'errorSection', 'resultsSection'].forEach(s => {
    const el = document.getElementById(s);
    if (s === id) {
      el.classList.remove('hidden'); el.classList.add('fade-in');
    } else {
      el.classList.add('hidden'); el.classList.remove('fade-in');
    }
  });
}
function resetToInput() {
  stopLoading();
  document.getElementById('tickerInput').value = '';
  showSection('hero');
  document.getElementById('tickerInput').focus();
}

// ── About modal ────────────────────────────────────────────────────────────────
function openAbout() {
  document.getElementById('aboutModal').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}
function closeAbout() {
  document.getElementById('aboutModal').classList.add('hidden');
  document.body.style.overflow = '';
}
function closeAboutOutside(e) {
  if (e.target === document.getElementById('aboutModal')) closeAbout();
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeAbout(); closeKeyModal(); }
});

// ── Formatting helpers ─────────────────────────────────────────────────────────
function fmtPrice(val) {
  if (val == null) return '—';
  if (val >= 1000) return `$${val.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  return `$${val.toFixed(2)}`;
}
function fmtLarge(val) {
  if (val == null) return '—';
  const abs = Math.abs(val), sign = val < 0 ? '-' : '';
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  return `${sign}$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}
function pct(val) {
  if (val == null) return '—';
  return `${Math.abs(val * 100).toFixed(1)}%`;
}
function pctSigned(val) {
  if (val == null) return '—';
  const v = val * 100;
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

// ── Deep Dive ──────────────────────────────────────────────────────────────────
function toggleDeepDive() {
  const panel   = document.getElementById('deepDivePanel');
  const chevron = document.getElementById('deepDiveChevron');
  const btnText = document.getElementById('deepDiveBtnText');
  const isHidden = panel.classList.contains('hidden');
  if (isHidden) {
    panel.classList.remove('hidden');
    chevron.classList.add('rotated');
    btnText.textContent = 'Hide Full Analysis';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } else {
    panel.classList.add('hidden');
    chevron.classList.remove('rotated');
    btnText.textContent = 'View Full Analysis';
  }
}
function switchTab(name) {
  ['dcf', 'interactive', 'comps', 'report', 'financials', 'rawdata'].forEach(t => {
    document.getElementById(`tab-${t}`).classList.toggle('active', t === name);
    document.getElementById(`pane-${t}`).classList.toggle('hidden', t !== name);
  });
}

let _currentData = null;

function populateDeepDive(data) {
  _currentData = data;
  const dcf = data.dcf_details   || {};
  const fin = data.financials_full || {};
  const raw = data.raw_data       || {};

  // DCF tab
  document.getElementById('dd-bull').textContent = dcf.bull ? fmtPrice(dcf.bull) : '—';
  document.getElementById('dd-base').textContent = dcf.base ? fmtPrice(dcf.base) : '—';
  document.getElementById('dd-bear').textContent = dcf.bear ? fmtPrice(dcf.bear) : '—';
  document.getElementById('dcfNote').textContent = dcf.note || '';

  const table = dcf.dcf_table;
  if (table && table.rows) {
    renderDCFTable(table, 'dcfTableBody', 'dcfTableFoot');
  } else {
    document.getElementById('dcfTableBody').innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:var(--text-3);padding:16px">DCF table unavailable (negative or missing FCF)</td></tr>';
  }

  initSliders(dcf, data.current_price);

  document.getElementById('compsContent').innerHTML =
    '<div class="comps-placeholder">Click "Load peer data" to view the full comps table.</div>';
  document.getElementById('loadCompsBtn').disabled = false;
  document.getElementById('loadCompsBtn').textContent = 'Load peer data →';

  document.getElementById('institutionalReport').innerHTML =
    renderMarkdown(data.institutional_report || 'Report not available.');

  const incomeRows = [
    { label: 'Revenue',          val: fmtLarge(fin.revenue) },
    { label: 'Revenue growth',   val: pctSigned(fin.revenue_growth), color: fin.revenue_growth },
    { label: 'Gross margin',     val: fin.gross_margin     ? pct(fin.gross_margin)     : '—' },
    { label: 'Operating margin', val: fin.operating_margin ? pct(fin.operating_margin) : '—' },
    { label: 'Net margin',       val: fin.profit_margin    ? pct(fin.profit_margin)    : '—', color: fin.profit_margin },
    { label: 'FCF margin',       val: fin.fcf_margin       ? pct(fin.fcf_margin)       : '—' },
    { label: 'Free cash flow',   val: fmtLarge(fin.free_cash_flow) },
  ];
  const balanceRows = [
    { label: 'Cash',          val: fmtLarge(fin.cash) },
    { label: 'Total debt',    val: fmtLarge(fin.total_debt) },
    { label: 'Debt / Equity', val: fin.debt_to_equity != null ? `${(fin.debt_to_equity).toFixed(0)}%` : '—' },
    { label: 'Current ratio', val: fin.current_ratio  != null ? `${fin.current_ratio.toFixed(2)}x`   : '—' },
  ];
  const multipleRows = [
    { label: 'P/E',       val: fin.pe_ratio   != null ? `${fin.pe_ratio.toFixed(1)}x`   : '—' },
    { label: 'P/B',       val: fin.pb_ratio   != null ? `${fin.pb_ratio.toFixed(2)}x`   : '—' },
    { label: 'P/S',       val: fin.ps_ratio   != null ? `${fin.ps_ratio.toFixed(2)}x`   : '—' },
    { label: 'EV/EBITDA', val: fin.ev_ebitda  != null ? `${fin.ev_ebitda.toFixed(1)}x`  : '—' },
    { label: 'EV/Revenue',val: fin.ev_revenue != null ? `${fin.ev_revenue.toFixed(2)}x` : '—' },
    { label: 'PEG',       val: fin.peg_ratio  != null ? `${fin.peg_ratio.toFixed(2)}x`  : '—' },
  ];
  const marketRows = [
    { label: 'Market cap',     val: fmtLarge(fin.market_cap) },
    { label: 'Enterprise val', val: fmtLarge(fin.enterprise_value) },
    { label: 'Shares out',     val: fin.shares_outstanding ? fmtLarge(fin.shares_outstanding) : '—' },
    { label: '52w high',       val: fin.fifty_two_week_high  ? fmtPrice(fin.fifty_two_week_high)  : '—' },
    { label: '52w low',        val: fin.fifty_two_week_low   ? fmtPrice(fin.fifty_two_week_low)   : '—' },
    { label: '1y return',      val: pctSigned(fin.price_return_1y), color: fin.price_return_1y },
    { label: 'Beta',           val: fin.beta          != null ? fin.beta.toFixed(2) : '—' },
    { label: 'Div yield',      val: fin.dividend_yield ? pct(fin.dividend_yield)   : '—' },
    { label: '# analysts',     val: fin.analyst_count  != null ? String(fin.analyst_count) : '—' },
  ];

  document.getElementById('finGrid-income').innerHTML    = renderFinRows(incomeRows);
  document.getElementById('finGrid-balance').innerHTML   = renderFinRows(balanceRows);
  document.getElementById('finGrid-multiples').innerHTML = renderFinRows(multipleRows);
  document.getElementById('finGrid-market').innerHTML    = renderFinRows(marketRows);

  populateRawData(raw);
}

// ── DCF Table renderer ─────────────────────────────────────────────────────────
function renderDCFTable(t, tbodyId, tfootId) {
  const tbody = document.getElementById(tbodyId);
  const tfoot = document.getElementById(tfootId);

  tbody.innerHTML = t.rows.map(r => `
    <tr>
      <td>Year ${r.year}</td>
      <td class="${r.growth_rate >= 0 ? 'pos' : 'neg'}">${pctSigned(r.growth_rate)}</td>
      <td>${fmtLarge(r.fcf)}</td>
      <td>${r.discount_factor.toFixed(4)}</td>
      <td>${fmtLarge(r.pv_fcf)}</td>
    </tr>`).join('') + `
    <tr class="dcf-subtotal">
      <td colspan="4">PV of Year 1–5 Cash Flows</td>
      <td>${fmtLarge(t.sum_pv_cashflows)}</td>
    </tr>
    <tr>
      <td>Terminal FCF</td>
      <td colspan="3">(Year 5 FCF × ${((t.terminal_growth || 0.03) * 100).toFixed(1)}% growth)</td>
      <td>${fmtLarge(t.terminal_fcf)}</td>
    </tr>
    <tr>
      <td>Terminal Value (undiscounted)</td>
      <td colspan="3">FCF / (WACC − g) = ${(t.wacc*100).toFixed(1)}% − ${((t.terminal_growth||0.03)*100).toFixed(1)}%</td>
      <td>${fmtLarge(t.terminal_value_gross)}</td>
    </tr>
    <tr class="dcf-subtotal">
      <td colspan="4">PV of Terminal Value</td>
      <td>${fmtLarge(t.pv_terminal)}</td>
    </tr>`;

  tfoot.innerHTML = `
    <tr class="dcf-total">
      <td colspan="4">Enterprise Value (PV FCFs + PV Terminal)</td>
      <td>${fmtLarge(t.enterprise_value)}</td>
    </tr>
    <tr>
      <td colspan="4">+ Cash</td>
      <td class="pos">${fmtLarge(t.cash)}</td>
    </tr>
    <tr>
      <td colspan="4">− Total Debt</td>
      <td class="neg">(${fmtLarge(t.total_debt)})</td>
    </tr>
    <tr class="dcf-total">
      <td colspan="4">Equity Value</td>
      <td>${fmtLarge(t.equity_value)}</td>
    </tr>
    <tr>
      <td colspan="4">÷ Shares Outstanding</td>
      <td>${fmtLarge(t.shares)}</td>
    </tr>
    <tr class="dcf-fairval">
      <td colspan="4">= Fair Value Per Share</td>
      <td>${t.fair_value ? fmtPrice(t.fair_value) : '—'}</td>
    </tr>`;
}

// ── Interactive DCF ────────────────────────────────────────────────────────────
let _dcfDefaults = {};

function initSliders(dcf, currentPrice) {
  const inputs = dcf.inputs || {};
  const baseGrowth = (inputs.growth_proxy || 0.10);
  _dcfDefaults = {
    wacc: (dcf.wacc || 0.10) * 100,
    g1:   baseGrowth * 100,
    fade: 75, tg: 3.0,
  };
  document.getElementById('sl-wacc').value = _dcfDefaults.wacc;
  document.getElementById('sl-g1').value   = _dcfDefaults.g1;
  document.getElementById('sl-fade').value = _dcfDefaults.fade;
  document.getElementById('sl-tg').value   = _dcfDefaults.tg;
  onSliderChange();
}
function resetSliders() {
  document.getElementById('sl-wacc').value = _dcfDefaults.wacc;
  document.getElementById('sl-g1').value   = _dcfDefaults.g1;
  document.getElementById('sl-fade').value = _dcfDefaults.fade;
  document.getElementById('sl-tg').value   = _dcfDefaults.tg;
  onSliderChange();
}
function onSliderChange() {
  const wacc = parseFloat(document.getElementById('sl-wacc').value) / 100;
  const g1   = parseFloat(document.getElementById('sl-g1').value)   / 100;
  const fade = parseFloat(document.getElementById('sl-fade').value) / 100;
  const tg   = parseFloat(document.getElementById('sl-tg').value)   / 100;

  document.getElementById('sv-wacc').textContent = `${(wacc*100).toFixed(1)}%`;
  document.getElementById('sv-g1').textContent   = `${(g1*100).toFixed(1)}%`;
  document.getElementById('sv-fade').textContent = `${(fade*100).toFixed(0)}%`;
  document.getElementById('sv-tg').textContent   = `${(tg*100).toFixed(1)}%`;

  if (!_currentData) return;
  const inputs  = _currentData.dcf_details?.inputs || {};
  const baseFCF = inputs.base_fcf, shares = inputs.shares;
  const cash    = inputs.cash || 0, debt = inputs.total_debt || 0;

  if (!baseFCF || !shares) {
    document.getElementById('ir-fairval').textContent = 'N/A (no FCF data)';
    return;
  }
  const result   = calcDCFClient(baseFCF, g1, fade, tg, wacc, cash, debt, shares);
  const fairVal  = result.fairValue;
  const curPrice = _currentData.current_price;

  document.getElementById('ir-fairval').textContent = fairVal ? fmtPrice(fairVal) : '—';
  if (fairVal && curPrice) {
    const ratio = curPrice / fairVal;
    const diff  = ((ratio - 1) * 100).toFixed(1);
    document.getElementById('ir-vs').textContent =
      `Current price ${fmtPrice(curPrice)} is ${Math.abs(diff)}% ${ratio > 1 ? 'above' : 'below'} this estimate`;
    let verdict, cls;
    if (ratio < 0.90)      { verdict = '🟢 Looks underpriced at these numbers'; cls = 'verdict-buy'; }
    else if (ratio > 1.15) { verdict = '🔴 Looks overpriced at these numbers';  cls = 'verdict-skip'; }
    else                   { verdict = '🟨 Looks fairly priced at these numbers'; cls = 'verdict-hold'; }
    const el = document.getElementById('ir-verdict');
    el.textContent = verdict;
    el.className   = `ir-verdict-badge ${cls}`;
  }
  renderDCFTable(result.table, 'interactiveTableBody', 'interactiveTableFoot');
}

function calcDCFClient(baseFCF, g1, fadeFactor, terminalGrowth, wacc, cash, debt, shares) {
  const growthRates = [];
  let g = g1;
  for (let i = 0; i < 5; i++) {
    growthRates.push(Math.max(-0.30, Math.min(g, 0.60)));
    g *= fadeFactor;
  }
  let fcf = baseFCF, sumPV = 0;
  const rows = [];
  for (let i = 0; i < growthRates.length; i++) {
    fcf = fcf * (1 + growthRates[i]);
    const df = 1 / Math.pow(1 + wacc, i + 1);
    const pv = fcf * df;
    sumPV += pv;
    rows.push({ year: i+1, growth_rate: growthRates[i], fcf, discount_factor: df, pv_fcf: pv });
  }
  const terminalFCF        = fcf * (1 + terminalGrowth);
  const terminalValueGross = terminalFCF / (wacc - terminalGrowth);
  const dfTerminal         = 1 / Math.pow(1 + wacc, 5);
  const pvTerminal         = terminalValueGross * dfTerminal;
  const ev                 = sumPV + pvTerminal;
  const equityValue        = ev + cash - debt;
  const fairValue          = shares > 0 ? Math.max(equityValue / shares, 0.01) : null;
  return {
    fairValue,
    table: {
      rows, wacc, terminal_growth: terminalGrowth,
      sum_pv_cashflows: sumPV, terminal_fcf: terminalFCF,
      terminal_value_gross: terminalValueGross, pv_terminal: pvTerminal,
      enterprise_value: ev, cash, total_debt: debt,
      equity_value: equityValue, shares, fair_value: fairValue,
    }
  };
}

// ── Comps ──────────────────────────────────────────────────────────────────────
async function _loadCompsEstimate() {
  if (!_currentData) return;
  try {
    const fin  = _currentData.financials_full || {};
    const resp = await fetch(`${API_BASE}/comps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker:  _currentData.ticker,
        sector:  _currentData.sector,
        industry: _currentData.raw_data?.identity?.industry || '',
        key:     localStorage.getItem('acAccessKey') || '',
        subject_metrics: {
          revenue:            fin.revenue,
          net_income:         _currentData.raw_data?.income_statement?.net_income,
          shares_outstanding: fin.shares_outstanding,
          enterprise_value:   fin.enterprise_value,
          total_equity:       _currentData.raw_data?.balance_sheet?.total_equity,
          ebit:               _currentData.raw_data?.income_statement?.ebit,
          cash:               fin.cash,
          total_debt:         fin.total_debt,
        }
      })
    });
    const data = await resp.json();
    if (data.error || !data.implied) throw new Error(data.error || 'no implied');
    const vals = Object.values(data.implied).filter(v => v != null && v > 0);
    if (vals.length === 0) throw new Error('no values');
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    document.getElementById('resCompsEstimate').textContent = fmtPrice(avg);
    _cachedCompsData = data;
  } catch {
    document.getElementById('resCompsEstimate').textContent = '—';
  }
}

let _cachedCompsData = null;

async function loadComps() {
  if (!_currentData) return;
  const btn = document.getElementById('loadCompsBtn');
  if (_cachedCompsData) { renderComps(_cachedCompsData); btn.textContent = '↺ Refresh'; return; }

  btn.disabled = true; btn.textContent = 'Loading peers...';
  document.getElementById('compsContent').innerHTML = `
    <div class="comps-loading">
      <div class="loading-spinner" style="width:32px;height:32px;margin:0 auto 12px"></div>
      <p>Fetching peer data — pulling ~5 companies from Yahoo Finance...</p>
    </div>`;
  try {
    const fin  = _currentData.financials_full || {};
    const resp = await fetch(`${API_BASE}/comps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker:  _currentData.ticker,
        sector:  _currentData.sector,
        industry: _currentData.raw_data?.identity?.industry || '',
        key:     localStorage.getItem('acAccessKey') || '',
        subject_metrics: {
          revenue:            fin.revenue,
          net_income:         _currentData.raw_data?.income_statement?.net_income,
          shares_outstanding: fin.shares_outstanding,
          enterprise_value:   fin.enterprise_value,
          total_equity:       _currentData.raw_data?.balance_sheet?.total_equity,
          ebit:               _currentData.raw_data?.income_statement?.ebit,
          cash:               fin.cash,
          total_debt:         fin.total_debt,
        }
      })
    });
    const compsData = await resp.json();
    if (compsData.error) throw new Error(compsData.error);
    renderComps(compsData);
    btn.textContent = '↺ Refresh'; btn.disabled = false;
  } catch(e) {
    document.getElementById('compsContent').innerHTML =
      `<div class="comps-placeholder" style="color:var(--red)">Failed to load: ${escapeHtml(e.message)}</div>`;
    btn.disabled = false; btn.textContent = 'Retry →';
  }
}

function renderComps(data) {
  const subject = _currentData;
  const peers   = data.peers   || {};
  const medians = data.medians || {};
  const implied = data.implied || {};

  const subjectRow = {
    ticker: subject.ticker, name: subject.name, price: subject.current_price,
    market_cap:       subject.financials_full?.market_cap,
    pe_ratio:         subject.financials_full?.pe_ratio,
    ev_ebitda:        subject.financials_full?.ev_ebitda,
    ps_ratio:         subject.financials_full?.ps_ratio,
    revenue_growth:   subject.financials_full?.revenue_growth,
    profit_margin:    subject.financials_full?.profit_margin,
    operating_margin: subject.financials_full?.operating_margin,
  };

  const cols = ['pe_ratio','ev_ebitda','ps_ratio','revenue_growth','profit_margin','operating_margin'];
  const colLabels = { pe_ratio:'P/E', ev_ebitda:'EV/EBITDA', ps_ratio:'P/S',
    revenue_growth:'Rev Growth', profit_margin:'Net Margin', operating_margin:'Op Margin' };

  const fmtMultiple = (v, key) => {
    if (v == null) return '<td>—</td>';
    const isGrowth = key.includes('growth') || key.includes('margin');
    const s   = isGrowth ? pctSigned(v) : `${v.toFixed(1)}x`;
    const cls = isGrowth ? (v >= 0 ? 'pos' : 'neg') : '';
    return `<td class="${cls}">${s}</td>`;
  };

  const buildRow = (row, isSubject, isMedian) => {
    const rowCls = isSubject ? 'subject-row' : (isMedian ? 'median-row' : '');
    return `<tr class="${rowCls}">
      <td><strong>${row.ticker}</strong></td>
      <td>${escapeHtml(row.name || '')}</td>
      <td>${row.price != null ? fmtPrice(row.price) : '—'}</td>
      <td>${row.market_cap != null ? fmtLarge(row.market_cap) : '—'}</td>
      ${cols.map(c => fmtMultiple(row[c], c)).join('')}
    </tr>`;
  };

  const peerList  = Array.isArray(peers) ? peers : Object.values(peers);
  const medianRow = { ticker: 'MEDIAN', name: '(peer median)', price: null, market_cap: null,
    ...Object.fromEntries(cols.map(c => [c, medians[c]])) };

  const impliedHtml = Object.keys(implied).length ? `
    <div class="comps-implied">
      <div class="comps-implied-title">Implied Share Price (at Peer Medians)</div>
      <div class="implied-grid">
        ${implied.pe_implied         != null ? `<div class="implied-item"><div class="implied-label">P/E Implied</div><div class="implied-val">${fmtPrice(implied.pe_implied)}</div></div>` : ''}
        ${implied.ps_implied         != null ? `<div class="implied-item"><div class="implied-label">P/S Implied</div><div class="implied-val">${fmtPrice(implied.ps_implied)}</div></div>` : ''}
        ${implied.ev_revenue_implied != null ? `<div class="implied-item"><div class="implied-label">EV/Rev Implied</div><div class="implied-val">${fmtPrice(implied.ev_revenue_implied)}</div></div>` : ''}
        ${implied.ev_ebitda_implied  != null ? `<div class="implied-item"><div class="implied-label">EV/EBITDA Implied</div><div class="implied-val">${fmtPrice(implied.ev_ebitda_implied)}</div></div>` : ''}
        ${implied.pb_implied         != null ? `<div class="implied-item"><div class="implied-label">P/B Implied</div><div class="implied-val">${fmtPrice(implied.pb_implied)}</div></div>` : ''}
      </div>
    </div>` : '';

  document.getElementById('compsContent').innerHTML = `
    <div class="comps-table-wrap">
      <table class="comps-table">
        <thead>
          <tr>
            <th>Ticker</th><th>Company</th><th>Price</th><th>Mkt Cap</th>
            ${cols.map(c => `<th>${colLabels[c]}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${buildRow(subjectRow, true, false)}
          ${peerList.map(p => buildRow(p, false, false)).join('')}
          ${buildRow(medianRow, false, true)}
        </tbody>
      </table>
    </div>
    ${impliedHtml}`;

  const impliedVals = Object.values(implied).filter(v => v != null && v > 0);
  if (impliedVals.length > 0) {
    const avg = impliedVals.reduce((a, b) => a + b, 0) / impliedVals.length;
    document.getElementById('resCompsEstimate').textContent = fmtPrice(avg);
  }
}

// ── Raw Data ───────────────────────────────────────────────────────────────────
function populateRawData(raw) {
  if (!raw) return;
  document.getElementById('rawSourceTag').textContent =
    `Source: ${raw.source || 'Yahoo Finance via yfinance'} · Data as of market close`;

  const renderRawSection = (sectionData, elId) => {
    if (!sectionData) return;
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = Object.entries(sectionData).map(([key, val]) => {
      const label  = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const isNull = val === null || val === undefined;
      let display;
      if (isNull) {
        display = '<span style="opacity:0.3">—</span>';
      } else if (typeof val === 'number') {
        if (Math.abs(val) > 1000) display = fmtLarge(val);
        else if (val > 0 && val < 1) display = `${(val*100).toFixed(2)}%`;
        else display = val.toFixed(4);
      } else {
        display = escapeHtml(String(val));
      }
      return `<div class="raw-item">
        <span class="raw-key">${label}</span>
        <span class="raw-val">${display}</span>
      </div>`;
    }).join('');
  };

  renderRawSection(raw.market,              'raw-market');
  renderRawSection(raw.income_statement,    'raw-income');
  renderRawSection(raw.margins,             'raw-margins');
  renderRawSection(raw.cash_flow,           'raw-cashflow');
  renderRawSection(raw.balance_sheet,       'raw-balance');
  renderRawSection(raw.valuation_multiples, 'raw-multiples');
  renderRawSection(raw.growth_and_risk,     'raw-growth');
  renderRawSection(raw.analyst_data,        'raw-analyst');
}

function renderFinRows(rows) {
  return rows.map(r => {
    let colorClass = '';
    if (r.color != null) colorClass = r.color >= 0 ? 'pos' : 'neg';
    return `<div class="fin-item">
      <div class="fin-label">${r.label}</div>
      <div class="fin-val ${colorClass}">${r.val}</div>
    </div>`;
  }).join('');
}
