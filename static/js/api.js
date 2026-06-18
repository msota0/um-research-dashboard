/* ═══════════════════════════════════════════════════════════════
   api.js — Fetch wrappers for all Flask API routes
   ═══════════════════════════════════════════════════════════════ */

const API = (() => {
  // Loading state tracking
  const _loading = {};
  let _dimErrorShown = false;
  let _oaErrorShown = false;

  function _showBanner(id, msg, type = 'warning') {
    const container = document.getElementById('errorBanners');
    if (!container || document.getElementById(id)) return;
    const div = document.createElement('div');
    div.id = id;
    div.className = `error-banner${type === 'error' ? ' error-critical' : ''} mb-2`;
    div.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> ${msg}`;
    container.appendChild(div);
  }

  function _clearBanner(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  async function _fetch(url, opts = {}) {
    const resp = await fetch(url, opts);
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw Object.assign(new Error(body.error || resp.statusText), { sourceError: body.source_error, status: resp.status });
    }
    return resp.json();
  }

  function _buildUrl(path, params = {}) {
    // Merge global year filter if present
    const state = window.AppState || {};
    const qs = new URLSearchParams();
    if (state.yearFrom) qs.set('year_from', state.yearFrom);
    if (state.yearTo) qs.set('year_to', state.yearTo);
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, v); });
    const q = qs.toString();
    return q ? `${path}?${q}` : path;
  }

  // Generic fetch with error handling and banner management
  async function call(path, params = {}, { skipYearFilter = false } = {}) {
    const url = skipYearFilter ? (params && Object.keys(params).length ? `${path}?${new URLSearchParams(params)}` : path) : _buildUrl(path, params);
    try {
      const data = await _fetch(url);
      // Clear any previous source error banners on success
      if (path.includes('openalex') || path.startsWith('/api/institution') ||
          path.startsWith('/api/publications') || path.startsWith('/api/authors') ||
          path.startsWith('/api/journals') || path.startsWith('/api/collaborations') ||
          path.startsWith('/api/open-access')) {
        _clearBanner('banner-openalex');
        _oaErrorShown = false;
      }
      if (path.startsWith('/api/grants') || path.startsWith('/api/trials') || path.startsWith('/api/patents')) {
        _clearBanner('banner-dimensions');
        _dimErrorShown = false;
      }
      return data;
    } catch (err) {
      if (err.sourceError === 'dimensions' && !_dimErrorShown) {
        _showBanner('banner-dimensions', 'Dimensions AI data temporarily unavailable. OpenAlex sections still active.');
        _dimErrorShown = true;
      } else if (err.sourceError === 'openalex' && !_oaErrorShown) {
        _showBanner('banner-openalex', 'OpenAlex data temporarily unavailable.', 'error');
        _oaErrorShown = true;
      } else if (!err.sourceError) {
        _showBanner('banner-network', `Network error: ${err.message}`);
      }
      throw err;
    }
  }

  // ── Public API methods ─────────────────────────────────────────
  return {
    institutionOverview: () => call('/api/institution/overview', {}, { skipYearFilter: true }),
    pubsByYear: () => call('/api/publications/by-year'),
    pubsByField: () => call('/api/publications/by-field'),
    pubsOpenAccess: () => call('/api/publications/open-access', {}, { skipYearFilter: true }),
    pubsByType: () => call('/api/publications/by-type'),
    pubsList: (page = 1, perPage = 25, type = '', yearFrom = '', yearTo = '') =>
      call('/api/publications/list', { page, per_page: perPage, type, year_from: yearFrom, year_to: yearTo }, { skipYearFilter: true }),
    authorsTop: (search = '') => call('/api/authors/top', search ? { search } : {}, { skipYearFilter: true }),
    authorWorks: (id) => call(`/api/authors/${id}/works`, {}, { skipYearFilter: true }),
    journalsTop: () => call('/api/journals/top', {}, { skipYearFilter: true }),
    collabInstitutions: () => call('/api/collaborations/institutions', {}, { skipYearFilter: true }),
    collabCountries: () => call('/api/collaborations/countries', {}, { skipYearFilter: true }),
    grantsSummary: () => call('/api/grants/summary', {}, { skipYearFilter: true }),
    grantsList: (page = 1, perPage = 25) => call('/api/grants/list', { page, per_page: perPage }, { skipYearFilter: true }),
    grantsByYear: () => call('/api/grants/by-year', {}, { skipYearFilter: true }),
    trialsSummary: () => call('/api/trials/summary', {}, { skipYearFilter: true }),
    trialsList: (page = 1, perPage = 25, search = '') =>
      call('/api/trials/list', { page, per_page: perPage, search }, { skipYearFilter: true }),
    patentsByYear: () => call('/api/patents/by-year', {}, { skipYearFilter: true }),
    patentsList: (page = 1, perPage = 25) => call('/api/patents/list', { page, per_page: perPage }, { skipYearFilter: true }),
    oaTrend: () => call('/api/open-access/trend', {}, { skipYearFilter: true }),
    cacheStatus: () => _fetch('/api/cache-status'),
  };
})();
