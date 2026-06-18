/* ═══════════════════════════════════════════════════════════════
   main.js — Tab switching, state management, data wiring
   ═══════════════════════════════════════════════════════════════ */

// ── Global state ────────────────────────────────────────────────
window.AppState = {
  activeTab: 'overview',
  yearFrom: 2000,
  yearTo: new Date().getFullYear(),
  initialized: {},   // tracks which tabs have loaded
  pubsPage: 1,
  grantsPage: 1,
  trialsPage: 1,
  patentsPage: 1,
  showDimComparison: false,
  dimPubsData: null,
  oaPubsData: null,
};

// ── Utility helpers ──────────────────────────────────────────────
function fmt(n) { return Charts.fmt(n); }

function fmtDate(s) {
  if (!s) return '—';
  return s.slice(0, 10);
}

function fmtUSD(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
  return '$' + n.toLocaleString();
}

function fmtTs(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function oaBadge(status) {
  const map = { gold: 'oa-gold', green: 'oa-green', hybrid: 'oa-hybrid', bronze: 'oa-bronze', closed: 'oa-closed' };
  const cls = map[status] || 'oa-closed';
  return `<span class="oa-badge ${cls}">${status || 'unknown'}</span>`;
}

function pagingHTML(page, total, perPage, onPrev, onNext) {
  const start = Math.min((page - 1) * perPage + 1, total);
  const end = Math.min(page * perPage, total);
  const totalPages = Math.ceil(total / perPage);
  return `
    <span class="paging-info">Showing ${start}–${end} of ${total.toLocaleString()}</span>
    <div class="d-flex gap-2">
      <button class="btn-paging" onclick="${onPrev}" ${page <= 1 ? 'disabled' : ''}>← Prev</button>
      <button class="btn-paging" onclick="${onNext}" ${page >= totalPages ? 'disabled' : ''}>Next →</button>
    </div>
  `;
}

function buildTable(columns, rows) {
  if (!rows || rows.length === 0) return '<div class="p-4 text-center text-muted">No data available.</div>';
  const thead = `<thead><tr>${columns.map(c => `<th>${c.label}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${rows.map(r =>
    `<tr${r._clickable ? ' class="clickable"' + (r._onclick ? ` onclick="${r._onclick}"` : '') : ''}>
      ${columns.map(c => `<td>${r[c.key] !== undefined && r[c.key] !== null ? r[c.key] : '—'}</td>`).join('')}
    </tr>`
  ).join('')}</tbody>`;
  return `<table class="um-table">${thead}${tbody}</table>`;
}

// ── CSV Export ───────────────────────────────────────────────────
window.downloadCSV = async function(section) {
  const today = new Date().toISOString().slice(0, 10);
  const filename = `um_research_${section}_${today}.csv`;
  let rows = [], headers = [];
  try {
    if (section === 'publications') {
      const resp = await API.pubsList(1, 1000);
      headers = ['Title', 'DOI', 'Year', 'Type', 'OA Status'];
      rows = (resp.data?.items || []).map(p => [p.title, p.doi || '', p.year || '', p.type || '', p.oa_status || '']);
    } else if (section === 'grants') {
      const resp = await API.grantsList(1, 1000);
      headers = ['Title', 'Funder', 'Funding (USD)', 'Start Date', 'End Date'];
      rows = (resp.data?.items || []).map(g => [g.title || '', g.funder_org_name || '', g.funding_usd || '', g.start_date || '', g.end_date || '']);
    } else if (section === 'trials') {
      const resp = await API.trialsList(1, 1000);
      headers = ['Title', 'Status', 'Phase', 'Date', 'Conditions'];
      rows = (resp.data?.items || []).map(t => [t.title || '', t.status || '', t.phase || '', t.date || '', (t.conditions || []).join('; ')]);
    } else if (section === 'patents') {
      const resp = await API.patentsList(1, 1000);
      headers = ['Title', 'Filing Date', 'Grant Date'];
      rows = (resp.data?.items || []).map(p => [p.title || '', p.filing_date || '', p.grant_date || '']);
    }
  } catch (e) { alert('Failed to export CSV: ' + e.message); return; }

  const escape = v => `"${String(v).replace(/"/g, '""')}"`;
  const csv = [headers.map(escape).join(','), ...rows.map(r => r.map(escape).join(','))].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = filename;
  a.click();
};

// ── Tab switching ────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.um-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tabId));
  document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.toggle('d-none', panel.id !== `tab-${tabId}`));
  AppState.activeTab = tabId;
  loadTab(tabId);
}

function loadTab(tabId) {
  if (AppState.initialized[tabId]) return;
  switch (tabId) {
    case 'overview':       loadOverview();       break;
    case 'publications':   loadPublications();   break;
    case 'fields':         loadFields();         break;
    case 'openaccess':     loadOpenAccess();     break;
    case 'authors':        loadAuthors();        break;
    case 'grants':         loadGrants();         break;
    case 'trials':         loadTrials();         break;
    case 'patents':        loadPatents();        break;
    case 'collaborations': loadCollaborations(); break;
    case 'journals':       loadJournals();       break;
  }
  AppState.initialized[tabId] = true;
}

// ── OVERVIEW ─────────────────────────────────────────────────────
async function loadOverview() {
  try {
    const [overviewResp, oaResp, grantsResp, pubsYearResp] = await Promise.allSettled([
      API.institutionOverview(),
      API.pubsOpenAccess(),
      API.grantsSummary(),
      API.pubsByYear(),
    ]);

    if (overviewResp.status === 'fulfilled') {
      const d = overviewResp.value.data;
      const ts = overviewResp.value.fetched_at;
      setVal('val-total-pubs', fmt(d.works_count));
      setVal('val-total-cites', fmt(d.cited_by_count));
      setVal('val-hindex', d.h_index ?? '—');
      setVal('val-i10index', `i10-index: ${fmt(d.i10_index)}`);
      document.getElementById('ts-openalex').textContent = 'Updated ' + fmtTs(ts);
      const sparkData = (d.counts_by_year || []).slice(-5).reverse().map(r => ({ year: r.year, count: r.works_count }));
      if (sparkData.length) Charts.sparkline('spark-pubs', sparkData);
      // Dims vs OA pub count comparison
      if (pubsYearResp.status === 'fulfilled') {
        const byYear = pubsYearResp.value.data;
        const oaTotal = (byYear?.openalex || []).reduce((a, b) => a + b.count, 0);
        const dimTotal = (byYear?.dimensions || []).reduce((a, b) => a + b.count, 0);
        if (dimTotal > 0) {
          document.getElementById('oa-pub-count').textContent = fmt(oaTotal);
          document.getElementById('dim-pub-count').textContent = fmt(dimTotal);
          document.getElementById('overview-pub-compare').style.display = 'block';
        }
      }
    }

    if (oaResp.status === 'fulfilled') {
      const oaData = oaResp.value.data || [];
      const total = oaData.reduce((s, d) => s + d.count, 0);
      const openCount = oaData.filter(d => d.oa_status !== 'closed').reduce((s, d) => s + d.count, 0);
      const pct = total > 0 ? ((openCount / total) * 100).toFixed(1) : '—';
      setVal('val-oa-pct', pct + '%');
    }

    if (grantsResp.status === 'fulfilled') {
      const g = grantsResp.value.data;
      setVal('val-total-grants', fmt(g.total_grants));
      setVal('val-total-funding', fmtUSD(g.total_funding_usd));
      document.getElementById('ts-dimensions').textContent = 'Updated ' + fmtTs(grantsResp.value.fetched_at);
      const topFunder = g.by_funder?.[0]?.name || '—';
      document.getElementById('val-top-funder').textContent = topFunder;
      // Funding sparkline via grants by year
      try {
        const gyResp = await API.grantsByYear();
        const gyData = (gyResp.data || []).slice(-5);
        if (gyData.length) Charts.fundingSparkline('spark-funding', gyData);
      } catch {}
    } else {
      setVal('val-total-grants', '—');
      setVal('val-total-funding', '—');
      document.getElementById('ts-dimensions').textContent = 'Unavailable';
    }

  } catch (e) {
    console.error('loadOverview error:', e);
  }
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.classList.remove('skeleton');
}

// ── PUBLICATIONS ─────────────────────────────────────────────────
async function loadPublications() {
  try {
    const resp = await API.pubsByYear();
    const data = resp.data;
    AppState.dimPubsData = data?.dimensions || [];
    AppState.oaPubsData = data?.openalex || [];
    Charts.pubsByYear('chart-pubs-year', AppState.oaPubsData, AppState.dimPubsData, false);
  } catch (e) { console.error('pubsByYear error:', e); }

  try {
    const resp = await API.pubsByType();
    Charts.pubsByType('chart-pubs-type', resp.data || []);
  } catch (e) { console.error('pubsByType error:', e); }

  loadPubsList();
}

async function loadPubsList() {
  const page = AppState.pubsPage;
  const type = document.getElementById('filter-pub-type')?.value || '';
  try {
    const resp = await API.pubsList(page, 25, type);
    const d = resp.data;
    const cols = [
      { key: 'title_link', label: 'Title' },
      { key: 'year', label: 'Year' },
      { key: 'type', label: 'Type' },
      { key: 'oa_badge', label: 'OA Status' },
    ];
    const rows = (d.items || []).map(p => ({
      title_link: p.doi ? `<a href="https://doi.org/${p.doi.replace('https://doi.org/', '')}" target="_blank">${p.title || '—'}</a>` : (p.title || '—'),
      year: p.year || '—',
      type: p.type || '—',
      oa_badge: oaBadge(p.oa_status),
    }));
    document.getElementById('table-pubs').innerHTML = buildTable(cols, rows);
    document.getElementById('paging-pubs').innerHTML = pagingHTML(page, d.total, 25,
      `AppState.pubsPage=${Math.max(1,page-1)};AppState.initialized.publications=false;loadPubsList()`,
      `AppState.pubsPage=${page+1};AppState.initialized.publications=false;loadPubsList()`
    );
  } catch (e) {
    document.getElementById('table-pubs').innerHTML = `<div class="p-3 text-danger">Failed to load publications.</div>`;
  }
}

// ── FIELDS ───────────────────────────────────────────────────────
async function loadFields() {
  try {
    const resp = await API.pubsByField();
    const data = resp.data || [];
    const labels = data.map(d => d.field_name.length > 35 ? d.field_name.slice(0, 33) + '…' : d.field_name);
    Charts.horizontalBar('chart-fields-bar', labels, data.map(d => d.count));
    Charts.donut('chart-fields-donut', data.slice(0, 8).map(d => d.field_name), data.slice(0, 8).map(d => d.count));
    const total = data.reduce((s, d) => s + d.count, 0);
    const cols = [
      { key: 'rank', label: '#' },
      { key: 'field_name', label: 'Field' },
      { key: 'count', label: 'Publications' },
      { key: 'pct', label: '% of Total' },
    ];
    const rows = data.map((d, i) => ({
      rank: `<span class="rank-badge">${i+1}</span>`,
      field_name: d.field_name,
      count: d.count.toLocaleString(),
      pct: total > 0 ? ((d.count / total) * 100).toFixed(1) + '%' : '—',
    }));
    document.getElementById('table-fields').innerHTML = buildTable(cols, rows);
  } catch (e) { console.error('loadFields error:', e); }
}

// ── OPEN ACCESS ───────────────────────────────────────────────────
async function loadOpenAccess() {
  try {
    const [oaResp, trendResp] = await Promise.allSettled([API.pubsOpenAccess(), API.oaTrend()]);
    if (oaResp.status === 'fulfilled') {
      const data = oaResp.value.data || [];
      Charts.oaDonut('chart-oa-donut', data);
      const total = data.reduce((s, d) => s + d.count, 0);
      const open = data.filter(d => d.oa_status !== 'closed').reduce((s, d) => s + d.count, 0);
      const pct = total > 0 ? ((open / total) * 100).toFixed(1) : 0;
      document.getElementById('oa-summary-sentence').textContent =
        `${pct}% of University of Mississippi research (${open.toLocaleString()} of ${total.toLocaleString()} publications) is openly accessible.`;
    }
    if (trendResp.status === 'fulfilled') {
      Charts.oaTrend('chart-oa-trend', trendResp.value.data || []);
    }
  } catch (e) { console.error('loadOpenAccess error:', e); }
}

// ── AUTHORS ───────────────────────────────────────────────────────
async function loadAuthors() {
  await renderAuthors();
}

async function renderAuthors(search = '') {
  try {
    const resp = await API.authorsTop(search);
    const data = resp.data || [];
    const cols = [
      { key: 'rank', label: '#' },
      { key: 'name', label: 'Name' },
      { key: 'works_count', label: 'Publications' },
      { key: 'cited_by_count', label: 'Citations' },
      { key: 'h_index', label: 'h-index' },
      { key: 'orcid_link', label: 'ORCID' },
    ];
    const rows = data.map((a, i) => ({
      rank: `<span class="rank-badge">${i+1}</span>`,
      name: a.name,
      works_count: fmt(a.works_count),
      cited_by_count: fmt(a.cited_by_count),
      h_index: a.h_index ?? '—',
      orcid_link: a.orcid ? `<a href="${a.orcid}" target="_blank" class="orcid-link"><i class="bi bi-person-badge"></i></a>` : '—',
      _clickable: true,
      _onclick: `openAuthorModal('${a.id}', '${a.name.replace(/'/g, "\\'")}')`,
    }));
    document.getElementById('table-authors').innerHTML = buildTable(cols, rows);
    // Initialize Bootstrap tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
  } catch (e) {
    document.getElementById('table-authors').innerHTML = `<div class="p-3 text-danger">Failed to load authors.</div>`;
  }
}

window.openAuthorModal = async function(authorId, name) {
  const modal = new bootstrap.Modal(document.getElementById('authorModal'));
  document.getElementById('authorModalLabel').textContent = name;
  document.getElementById('authorModalBody').innerHTML = '<div class="text-center py-3"><div class="spinner-border text-danger"></div></div>';
  modal.show();
  try {
    const resp = await API.authorWorks(authorId);
    const works = resp.data || [];
    if (works.length === 0) {
      document.getElementById('authorModalBody').innerHTML = '<div class="text-muted p-3">No works found.</div>';
      return;
    }
    const html = `<h6 class="text-muted mb-3">Top publications</h6>
      <ul class="list-group list-group-flush">
        ${works.map(w => `
          <li class="list-group-item px-0">
            <div class="fw-semibold small">${w.doi ? `<a href="https://doi.org/${w.doi.replace('https://doi.org/', '')}" target="_blank">${w.title || '—'}</a>` : (w.title || '—')}</div>
            <div class="text-muted" style="font-size:0.78rem">${w.year || '—'} &nbsp;·&nbsp; ${w.citations || 0} citations</div>
          </li>`).join('')}
      </ul>`;
    document.getElementById('authorModalBody').innerHTML = html;
  } catch (e) {
    document.getElementById('authorModalBody').innerHTML = `<div class="text-danger p-3">Failed to load works: ${e.message}</div>`;
  }
};

// ── GRANTS ────────────────────────────────────────────────────────
async function loadGrants() {
  try {
    const [summResp, byYearResp] = await Promise.allSettled([API.grantsSummary(), API.grantsByYear()]);
    if (summResp.status === 'fulfilled') {
      const g = summResp.value.data;
      setVal('val-grants-total', fmt(g.total_grants));
      setVal('val-grants-funding', fmtUSD(g.total_funding_usd));
      const top = g.by_funder?.[0];
      setVal('val-grants-top-funder', top ? `${top.name} (${fmtUSD(top.total_usd)})` : '—');
      Charts.grantsFunders('chart-grants-funders', g.by_funder || []);
    }
    if (byYearResp.status === 'fulfilled') {
      Charts.grantsByYear('chart-grants-year', byYearResp.value.data || []);
    }
  } catch (e) { console.error('loadGrants error:', e); }
  loadGrantsList();
}

async function loadGrantsList() {
  try {
    const resp = await API.grantsList(AppState.grantsPage, 25);
    const d = resp.data;
    const cols = [
      { key: 'title', label: 'Title' },
      { key: 'funder_org_name', label: 'Funder' },
      { key: 'funding', label: 'Amount' },
      { key: 'start_date', label: 'Start' },
      { key: 'end_date', label: 'End' },
    ];
    const rows = (d.items || []).map(g => ({
      title: g.title || '—',
      funder_org_name: g.funder_org_name || '—',
      funding: fmtUSD(g.funding_usd),
      start_date: fmtDate(g.start_date),
      end_date: fmtDate(g.end_date),
    }));
    document.getElementById('table-grants').innerHTML = buildTable(cols, rows);
    document.getElementById('paging-grants').innerHTML = pagingHTML(
      AppState.grantsPage, d.total, 25,
      `AppState.grantsPage=Math.max(1,${AppState.grantsPage}-1);AppState.initialized.grants=false;loadGrantsList()`,
      `AppState.grantsPage=${AppState.grantsPage+1};AppState.initialized.grants=false;loadGrantsList()`
    );
  } catch (e) {
    document.getElementById('table-grants').innerHTML = `<div class="p-3 text-danger">Dimensions AI data unavailable for grants.</div>`;
  }
}

// ── CLINICAL TRIALS ───────────────────────────────────────────────
async function loadTrials() {
  try {
    const resp = await API.trialsSummary();
    const d = resp.data;
    setVal('val-trials-total', fmt(d.total));
    setVal('val-trials-active', fmt(d.active_count));
    setVal('val-trials-completed', fmt(d.completed_count));
    setVal('val-trials-recruiting', fmt(d.recruiting_count));
    Charts.trialsByPhase('chart-trials-phase', d.by_phase || []);
  } catch (e) { console.error('loadTrials summary error:', e); }
  loadTrialsList();
}

async function loadTrialsList(search = '') {
  try {
    const resp = await API.trialsList(AppState.trialsPage, 25, search);
    const d = resp.data;
    const cols = [
      { key: 'title', label: 'Title' },
      { key: 'status', label: 'Status' },
      { key: 'phase', label: 'Phase' },
      { key: 'date', label: 'Date' },
      { key: 'conditions_str', label: 'Conditions' },
    ];
    const rows = (d.items || []).map(t => ({
      title: t.title || '—',
      status: t.status || '—',
      phase: t.phase || '—',
      date: fmtDate(t.date),
      conditions_str: (t.conditions || []).slice(0, 2).join(', ') || '—',
    }));
    document.getElementById('table-trials').innerHTML = buildTable(cols, rows);
    document.getElementById('paging-trials').innerHTML = pagingHTML(
      AppState.trialsPage, d.total, 25,
      `AppState.trialsPage=Math.max(1,${AppState.trialsPage}-1);AppState.initialized.trials=false;loadTrialsList()`,
      `AppState.trialsPage=${AppState.trialsPage+1};AppState.initialized.trials=false;loadTrialsList()`
    );
  } catch (e) {
    document.getElementById('table-trials').innerHTML = `<div class="p-3 text-danger">Dimensions AI data unavailable for clinical trials.</div>`;
  }
}

// ── PATENTS ───────────────────────────────────────────────────────
async function loadPatents() {
  try {
    const resp = await API.patentsByYear();
    const data = resp.data || [];
    const total = data.reduce((s, d) => s + d.count, 0);
    setVal('val-patents-total', fmt(total));
    Charts.patentsByYear('chart-patents-year', data);
  } catch (e) { console.error('loadPatents error:', e); }
  loadPatentsList();
}

async function loadPatentsList() {
  try {
    const resp = await API.patentsList(AppState.patentsPage, 25);
    const d = resp.data;
    const cols = [
      { key: 'title', label: 'Title' },
      { key: 'filing_date', label: 'Filing Date' },
      { key: 'grant_date', label: 'Grant Date' },
    ];
    const rows = (d.items || []).map(p => ({
      title: p.title || '—',
      filing_date: fmtDate(p.filing_date),
      grant_date: fmtDate(p.grant_date),
    }));
    document.getElementById('table-patents').innerHTML = buildTable(cols, rows);
    document.getElementById('paging-patents').innerHTML = pagingHTML(
      AppState.patentsPage, d.total, 25,
      `AppState.patentsPage=Math.max(1,${AppState.patentsPage}-1);AppState.initialized.patents=false;loadPatentsList()`,
      `AppState.patentsPage=${AppState.patentsPage+1};AppState.initialized.patents=false;loadPatentsList()`
    );
  } catch (e) {
    document.getElementById('table-patents').innerHTML = `<div class="p-3 text-danger">Dimensions AI data unavailable for patents.</div>`;
  }
}

// ── COLLABORATIONS ────────────────────────────────────────────────
async function loadCollaborations() {
  try {
    const [instResp, countryResp] = await Promise.allSettled([API.collabInstitutions(), API.collabCountries()]);
    if (instResp.status === 'fulfilled') {
      const data = instResp.value.data || [];
      const labels = data.map(d => d.name.length > 40 ? d.name.slice(0, 38) + '…' : d.name);
      Charts.horizontalBar('chart-collab-inst', labels, data.map(d => d.count));
    }
    if (countryResp.status === 'fulfilled') {
      const data = (countryResp.value.data || []).slice(0, 15);
      Charts.horizontalBar('chart-collab-countries', data.map(d => d.country), data.map(d => d.count));
    }
  } catch (e) { console.error('loadCollaborations error:', e); }
}

// ── JOURNALS ──────────────────────────────────────────────────────
async function loadJournals() {
  try {
    const resp = await API.journalsTop();
    const data = resp.data || [];
    const labels = data.map(d => d.name.length > 40 ? d.name.slice(0, 38) + '…' : d.name);
    Charts.horizontalBar('chart-journals-bar', labels, data.map(d => d.count));
    renderJournalsTable(data);
  } catch (e) { console.error('loadJournals error:', e); }
}

function renderJournalsTable(data, filter = '') {
  const filtered = filter ? data.filter(d => d.name.toLowerCase().includes(filter.toLowerCase())) : data;
  const cols = [
    { key: 'rank', label: '#' },
    { key: 'name', label: 'Journal' },
    { key: 'count', label: 'Publications' },
  ];
  const rows = filtered.map((d, i) => ({
    rank: `<span class="rank-badge">${i+1}</span>`,
    name: d.name,
    count: d.count.toLocaleString(),
  }));
  document.getElementById('table-journals').innerHTML = buildTable(cols, rows);
}

// ── GLOBAL SEARCH ─────────────────────────────────────────────────
let _searchTimeout;
const searchInput = document.getElementById('globalSearch');
const searchDropdown = document.getElementById('searchDropdown');

if (searchInput) {
  searchInput.addEventListener('input', () => {
    clearTimeout(_searchTimeout);
    const q = searchInput.value.trim();
    if (q.length < 2) { searchDropdown.classList.add('d-none'); return; }
    _searchTimeout = setTimeout(() => performSearch(q), 350);
  });

  document.addEventListener('click', e => {
    if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
      searchDropdown.classList.add('d-none');
    }
  });
}

async function performSearch(q) {
  const results = [];
  const [pubsResp, authResp] = await Promise.allSettled([
    API.pubsList(1, 5, '', '', ''),
    API.authorsTop(q),
  ]);
  if (authResp.status === 'fulfilled') {
    for (const a of (authResp.value.data || []).slice(0, 4)) {
      if (a.name.toLowerCase().includes(q.toLowerCase())) {
        results.push({ type: 'author', label: a.name, sub: `${fmt(a.works_count)} publications`, tab: 'authors' });
      }
    }
  }
  if (pubsResp.status === 'fulfilled') {
    for (const p of (pubsResp.value.data?.items || [])) {
      if ((p.title || '').toLowerCase().includes(q.toLowerCase())) {
        results.push({ type: 'pub', label: p.title, sub: `${p.year || ''} · ${p.type || ''}`, tab: 'publications' });
      }
    }
  }
  if (results.length === 0) {
    searchDropdown.innerHTML = '<div class="search-result-item text-muted">No results found.</div>';
  } else {
    searchDropdown.innerHTML = results.slice(0, 6).map(r =>
      `<div class="search-result-item" onclick="switchTab('${r.tab}');searchDropdown.classList.add('d-none');searchInput.value=''">
        <span class="result-type">${r.type}</span>${r.label}
        <div class="text-muted" style="font-size:0.7rem">${r.sub}</div>
      </div>`
    ).join('');
  }
  searchDropdown.classList.remove('d-none');
}

// ── YEAR SLIDER ────────────────────────────────────────────────────
const sliderEl = document.getElementById('yearSlider');
const currentYear = new Date().getFullYear();
document.getElementById('maxYearLabel').textContent = currentYear;

if (sliderEl && typeof noUiSlider !== 'undefined') {
  noUiSlider.create(sliderEl, {
    start: [2000, currentYear],
    connect: true,
    step: 1,
    range: { min: 2000, max: currentYear },
    tooltips: false,
  });
  sliderEl.noUiSlider.on('update', values => {
    AppState.yearFrom = Math.round(values[0]);
    AppState.yearTo = Math.round(values[1]);
    document.getElementById('yearRangeLabel').innerHTML =
      `${AppState.yearFrom}–<span id="maxYearLabel">${AppState.yearTo}</span>`;
  });
  sliderEl.noUiSlider.on('change', () => {
    // Invalidate year-sensitive tabs
    ['publications', 'fields', 'openaccess', 'collaborations'].forEach(t => {
      delete AppState.initialized[t];
    });
    if (['publications', 'fields', 'openaccess', 'collaborations'].includes(AppState.activeTab)) {
      loadTab(AppState.activeTab);
    }
  });
}

// ── EVENT LISTENERS ───────────────────────────────────────────────
document.querySelectorAll('.um-tab').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

const dimToggle = document.getElementById('btn-dim-compare');
if (dimToggle) {
  dimToggle.addEventListener('click', () => {
    AppState.showDimComparison = !AppState.showDimComparison;
    dimToggle.textContent = AppState.showDimComparison ? 'Hide Dimensions Comparison' : 'Show Dimensions Comparison';
    Charts.pubsByYear('chart-pubs-year', AppState.oaPubsData || [], AppState.dimPubsData || [], AppState.showDimComparison);
  });
}

const filterPubType = document.getElementById('filter-pub-type');
if (filterPubType) {
  filterPubType.addEventListener('change', () => {
    AppState.pubsPage = 1;
    loadPubsList();
  });
}

const authorSearch = document.getElementById('author-search');
if (authorSearch) {
  let _authTimeout;
  authorSearch.addEventListener('input', () => {
    clearTimeout(_authTimeout);
    _authTimeout = setTimeout(() => renderAuthors(authorSearch.value.trim()), 400);
  });
}

const trialSearch = document.getElementById('trial-search');
if (trialSearch) {
  let _trialTimeout;
  trialSearch.addEventListener('input', () => {
    clearTimeout(_trialTimeout);
    _trialTimeout = setTimeout(() => { AppState.trialsPage = 1; loadTrialsList(trialSearch.value.trim()); }, 400);
  });
}

const journalSearch = document.getElementById('journal-search');
let _journalData = [];
if (journalSearch) {
  journalSearch.addEventListener('input', () => {
    renderJournalsTable(_journalData, journalSearch.value.trim());
  });
}

// Patch loadJournals to cache data for search
const _origLoadJournals = loadJournals;
async function loadJournals() {
  try {
    const resp = await API.journalsTop();
    _journalData = resp.data || [];
    const labels = _journalData.map(d => d.name.length > 40 ? d.name.slice(0, 38) + '…' : d.name);
    Charts.horizontalBar('chart-journals-bar', labels, _journalData.map(d => d.count));
    renderJournalsTable(_journalData);
  } catch (e) { console.error('loadJournals error:', e); }
}

// Initialize Bootstrap tooltips
document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));

// ── BOOT ──────────────────────────────────────────────────────────
switchTab('overview');
