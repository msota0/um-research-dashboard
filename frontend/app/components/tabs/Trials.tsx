'use client';
import { useEffect, useState, useCallback } from 'react';
import { api, Trial, TrialsSummary } from '../../../lib/api';
import { fmt, fmtDate, downloadCSV, today } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import StatCard from '../StatCard';
import DataTable, { Column } from '../DataTable';
import Pagination from '../Pagination';
import Skeleton from '../Skeleton';
import PieChart from '../charts/PieChart';
import styles from './Trials.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Trials({ onDimError }: Props) {
  const [summary, setSummary] = useState<TrialsSummary | null>(null);
  const [items, setItems] = useState<Trial[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(true);
  let _timer: ReturnType<typeof setTimeout>;

  useEffect(() => {
    api.trialsSummary()
      .then(r => setSummary(r.data))
      .catch(() => onDimError())
      .finally(() => setLoading(false));
  }, []);

  const loadList = useCallback(async (p: number, q: string) => {
    setListLoading(true);
    try {
      const res = await api.trialsList(p, 25, q);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch { onDimError(); }
    finally { setListLoading(false); }
  }, []);

  useEffect(() => { loadList(page, search); }, [page, loadList]);

  const handleSearch = (q: string) => {
    setSearch(q);
    clearTimeout(_timer);
    _timer = setTimeout(() => { setPage(1); loadList(1, q); }, 400);
  };

  const handleExport = async () => {
    try {
      const res = await api.trialsList(1, 1000, search);
      downloadCSV(
        `um_research_trials_${today()}.csv`,
        ['Title', 'Status', 'Phase', 'Date', 'Conditions'],
        res.data.items.map(t => [t.title, t.status, t.phase, t.date, (t.conditions ?? []).join('; ')])
      );
    } catch {}
  };

  const phaseColors = ['#CE1126','#002147','#2980B9','#27AE60','#F5A623','#8E44AD','#7F8C8D'];

  const columns: Column<Trial>[] = [
    { key: 'title', label: 'Title', render: v => <span style={{ fontWeight: 500 }}>{String(v ?? '—')}</span> },
    { key: 'status', label: 'Status', render: v => <span className={`${styles.statusBadge} ${styles[`status_${String(v ?? '').toLowerCase().replace(/\s+/g, '_')}`] ?? ''}`}>{String(v ?? '—')}</span> },
    { key: 'phase', label: 'Phase' },
    { key: 'date', label: 'Date', render: v => fmtDate(String(v ?? '')) },
    { key: 'conditions', label: 'Conditions', render: v => ((v as string[] | undefined) ?? []).slice(0, 2).join(', ') || '—' },
  ];

  return (
    <div className={`${styles.root} fadeInUp`}>
      {/* Stat cards */}
      <div className={styles.statGrid}>
        <StatCard label="Total Trials" value={summary ? fmt(summary.total) : undefined} source="dimensions" loading={loading} />
        <StatCard label="Active" value={summary ? fmt(summary.active_count) : undefined} source="dimensions" loading={loading} />
        <StatCard label="Completed" value={summary ? fmt(summary.completed_count) : undefined} source="dimensions" loading={loading} />
        <StatCard label="Recruiting" value={summary ? fmt(summary.recruiting_count) : undefined} source="dimensions" loading={loading} />
      </div>

      {/* Phase chart + list */}
      <div className={styles.content}>
        <ChartCard title="Trials by Phase" source="dimensions">
          {summary
            ? <div style={{ height: 280 }}>
                <PieChart
                  labels={(summary.by_phase ?? []).map(d => d.phase || 'N/A')}
                  data={(summary.by_phase ?? []).map(d => d.count)}
                  colors={phaseColors}
                />
              </div>
            : <Skeleton height={280} />
          }
        </ChartCard>

        <div className={styles.listPanel}>
          <div className={styles.listHeader}>
            <h3 className={styles.listTitle}>Trial List</h3>
            <div className={styles.listActions}>
              <input
                className={styles.searchInput}
                type="search"
                placeholder="Search trials…"
                value={search}
                onChange={e => handleSearch(e.target.value)}
              />
              <button className={styles.csvBtn} onClick={handleExport}>⬇ CSV</button>
            </div>
          </div>
          {listLoading
            ? <Skeleton height={300} borderRadius={0} />
            : <DataTable columns={columns} rows={items} emptyMessage="No clinical trials found." />
          }
          <Pagination page={page} total={total} perPage={25} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
        </div>
      </div>
    </div>
  );
}
