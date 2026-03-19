export function fmt(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString();
}

export function fmtUSD(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return '$' + Math.round(n / 1e3) + 'K';
  return '$' + n.toLocaleString();
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return '—';
  return s.slice(0, 10);
}

export function fmtTs(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function oaClass(status: string): string {
  const map: Record<string, string> = {
    gold: 'oaBadge--gold', green: 'oaBadge--green',
    hybrid: 'oaBadge--hybrid', bronze: 'oaBadge--bronze',
    closed: 'oaBadge--closed', diamond: 'oaBadge--diamond',
  };
  return `oaBadge ${map[status] ?? 'oaBadge--unknown'}`;
}

export const CHART_COLORS = [
  '#CE1126','#002147','#2980B9','#27AE60','#F5A623',
  '#8E44AD','#16A085','#E67E22','#2C3E50','#C0392B',
  '#1ABC9C','#D35400','#3498DB','#7F8C8D','#117A65',
  '#E74C3C','#9B59B6','#F39C12','#1A5276','#CB4335',
];

export const OA_COLORS: Record<string, string> = {
  gold: '#F5A623', green: '#27AE60', hybrid: '#2980B9',
  bronze: '#E67E22', closed: '#7F8C8D', diamond: '#1ABC9C', unknown: '#BDC3C7',
};

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function downloadCSV(filename: string, headers: string[], rows: (string | number | undefined | null)[][]) {
  const escape = (v: string | number | undefined | null) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [headers.map(escape).join(','), ...rows.map(r => r.map(escape).join(','))].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = filename;
  a.click();
}
