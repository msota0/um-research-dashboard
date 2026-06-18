/* ═══════════════════════════════════════════════════════════════
   charts.js — Chart.js visualisations
   ═══════════════════════════════════════════════════════════════ */

const Charts = (() => {
  const _instances = {};

  const UM_RED   = '#CE1126';
  const UM_NAVY  = '#002147';
  const UM_COLORS = [
    '#CE1126','#002147','#2980B9','#27AE60','#F5A623',
    '#8E44AD','#16A085','#E67E22','#2C3E50','#C0392B',
    '#1ABC9C','#D35400','#3498DB','#7F8C8D','#27AE60',
    '#E74C3C','#9B59B6','#F39C12','#1A5276','#117A65'
  ];

  const OA_COLORS = {
    gold: '#F5A623',
    green: '#27AE60',
    hybrid: '#2980B9',
    bronze: '#E67E22',
    closed: '#7F8C8D',
    unknown: '#BDC3C7',
    diamond: '#1ABC9C',
  };

  const DEFAULTS = {
    font: { family: "'Segoe UI', system-ui, sans-serif" },
    plugins: {
      legend: { labels: { font: { family: "'Segoe UI', system-ui, sans-serif", size: 12 } } },
      tooltip: { callbacks: {} },
    },
    responsive: true,
    maintainAspectRatio: false,
  };

  function _destroy(id) {
    if (_instances[id]) {
      _instances[id].destroy();
      delete _instances[id];
    }
  }

  function _get(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    _destroy(id);
    return el.getContext('2d');
  }

  function _fmt(n) {
    if (n === null || n === undefined) return '—';
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toLocaleString();
  }

  // ── Sparkline (tiny line chart for stat cards) ──────────────────
  function sparkline(id, data, color = UM_RED) {
    const ctx = _get(id);
    if (!ctx) return;
    _instances[id] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(d => d.year),
        datasets: [{ data: data.map(d => d.count), borderColor: color, borderWidth: 2,
          fill: true, backgroundColor: color + '22', tension: 0.4, pointRadius: 0 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
        animation: { duration: 600 },
      },
    });
  }

  // ── Bar chart (publications per year) ───────────────────────────
  function pubsByYear(id, oaData, dimData = null, showDim = false) {
    const ctx = _get(id);
    if (!ctx) return;
    const labels = oaData.map(d => d.year);
    const datasets = [
      {
        label: 'OpenAlex',
        data: oaData.map(d => d.count),
        backgroundColor: UM_RED + 'CC',
        borderColor: UM_RED,
        borderWidth: 1,
        borderRadius: 4,
      }
    ];
    if (showDim && dimData && dimData.length > 0) {
      datasets.push({
        label: 'Dimensions AI',
        data: dimData.map(d => {
          const match = oaData.find(o => String(o.year) === String(d.year));
          return d.count;
        }),
        type: 'line',
        borderColor: UM_NAVY,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.3,
      });
    }
    _instances[id] = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets },
      options: {
        ...DEFAULTS,
        plugins: {
          ...DEFAULTS.plugins,
          legend: { display: showDim && !!dimData, position: 'top' },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 11 } } },
          y: { beginAtZero: true, grid: { color: '#f0f0f0' },
               ticks: { callback: v => _fmt(v) } },
        },
      },
    });
    return _instances[id];
  }

  // ── Publication type bar chart ───────────────────────────────────
  function pubsByType(id, data) {
    const ctx = _get(id);
    if (!ctx) return;
    _instances[id] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.map(d => d.type),
        datasets: [{ data: data.map(d => d.count), backgroundColor: UM_COLORS.slice(0, data.length),
          borderRadius: 4 }]
      },
      options: {
        ...DEFAULTS,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 11 } } },
          y: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { callback: v => _fmt(v) } },
        },
      },
    });
  }

  // ── Horizontal bar chart (fields, journals, collaborations) ──────
  function horizontalBar(id, labels, data, colors = null) {
    const ctx = _get(id);
    if (!ctx) return;
    const bgColors = colors || labels.map((_, i) => UM_COLORS[i % UM_COLORS.length]);
    _instances[id] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ data, backgroundColor: bgColors, borderRadius: 3 }]
      },
      options: {
        ...DEFAULTS,
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { callback: v => _fmt(v) } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } },
        },
      },
    });
  }

  // ── Donut chart ──────────────────────────────────────────────────
  function donut(id, labels, data, colors = null) {
    const ctx = _get(id);
    if (!ctx) return;
    const bgColors = colors || labels.map((_, i) => UM_COLORS[i % UM_COLORS.length]);
    _instances[id] = new Chart(ctx, {
      type: 'doughnut',
      data: { labels, datasets: [{ data, backgroundColor: bgColors, borderWidth: 2, borderColor: '#fff' }] },
      options: {
        ...DEFAULTS,
        cutout: '60%',
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 }, boxWidth: 14, padding: 10 } },
          tooltip: {
            callbacks: {
              label: ctx => {
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                return ` ${ctx.label}: ${_fmt(ctx.raw)} (${pct}%)`;
              }
            }
          }
        },
      },
    });
  }

  // ── OA Donut with fixed colors ───────────────────────────────────
  function oaDonut(id, data) {
    const labels = data.map(d => d.oa_status.charAt(0).toUpperCase() + d.oa_status.slice(1));
    const values = data.map(d => d.count);
    const colors = data.map(d => OA_COLORS[d.oa_status] || OA_COLORS.unknown);
    donut(id, labels, values, colors);
  }

  // ── OA Trend line chart ──────────────────────────────────────────
  function oaTrend(id, data) {
    const ctx = _get(id);
    if (!ctx) return;
    _instances[id] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(d => d.year),
        datasets: [{
          label: 'OA %',
          data: data.map(d => d.oa_percentage),
          borderColor: OA_COLORS.green,
          backgroundColor: OA_COLORS.green + '22',
          fill: true,
          tension: 0.35,
          pointBackgroundColor: OA_COLORS.green,
          pointRadius: 4,
        }]
      },
      options: {
        ...DEFAULTS,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => ` ${ctx.raw.toFixed(1)}%` } }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, max: 100, grid: { color: '#f0f0f0' },
               ticks: { callback: v => v + '%' } },
        },
      },
    });
  }

  // ── Grants funders bar ───────────────────────────────────────────
  function grantsFunders(id, data) {
    const ctx = _get(id);
    if (!ctx) return;
    const labels = data.map(d => d.name.length > 30 ? d.name.slice(0, 28) + '…' : d.name);
    _instances[id] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ data: data.map(d => d.total_usd), backgroundColor: UM_RED + 'CC',
          borderColor: UM_RED, borderWidth: 1, borderRadius: 3 }]
      },
      options: {
        ...DEFAULTS,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => ` $${_fmt(ctx.raw)}` } }
        },
        scales: {
          x: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { callback: v => '$' + _fmt(v) } },
          y: { grid: { display: false }, ticks: { font: { size: 10 } } },
        },
      },
    });
  }

  // ── Grants by year line ──────────────────────────────────────────
  function grantsByYear(id, data) {
    const ctx = _get(id);
    if (!ctx) return;
    _instances[id] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(d => d.year),
        datasets: [{
          label: 'Total Funding (USD)',
          data: data.map(d => d.total_usd),
          borderColor: UM_NAVY,
          backgroundColor: UM_NAVY + '22',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
        }]
      },
      options: {
        ...DEFAULTS,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => ` $${_fmt(ctx.raw)}` } }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { callback: v => '$' + _fmt(v) } },
        },
      },
    });
  }

  // ── Trials by phase pie ──────────────────────────────────────────
  function trialsByPhase(id, data) {
    const labels = data.map(d => d.phase || 'N/A');
    const values = data.map(d => d.count);
    const colors = ['#CE1126','#002147','#2980B9','#27AE60','#F5A623','#8E44AD','#7F8C8D'];
    const ctx = _get(id);
    if (!ctx) return;
    _instances[id] = new Chart(ctx, {
      type: 'pie',
      data: { labels, datasets: [{ data: values, backgroundColor: colors.slice(0, labels.length), borderWidth: 2, borderColor: '#fff' }] },
      options: {
        ...DEFAULTS,
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 }, boxWidth: 14 } },
          tooltip: {
            callbacks: {
              label: ctx => {
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                return ` ${ctx.label}: ${ctx.raw} (${((ctx.raw/total)*100).toFixed(1)}%)`;
              }
            }
          }
        },
      },
    });
  }

  // ── Patents by year bar ──────────────────────────────────────────
  function patentsByYear(id, data) {
    const ctx = _get(id);
    if (!ctx) return;
    _instances[id] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.map(d => d.year),
        datasets: [{ data: data.map(d => d.count), backgroundColor: UM_NAVY + 'CC',
          borderColor: UM_NAVY, borderWidth: 1, borderRadius: 4 }]
      },
      options: {
        ...DEFAULTS,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { stepSize: 1 } },
        },
      },
    });
  }

  // ── Sparkline for funding ────────────────────────────────────────
  function fundingSparkline(id, data) {
    sparkline(id, data.map(d => ({ year: d.year, count: d.total_usd })), UM_NAVY);
  }

  return {
    sparkline, pubsByYear, pubsByType, horizontalBar, donut, oaDonut, oaTrend,
    grantsFunders, grantsByYear, trialsByPhase, patentsByYear, fundingSparkline,
    getInstance: id => _instances[id],
    fmt: _fmt,
  };
})();
