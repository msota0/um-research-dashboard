'use client';
import { useEffect, useState, useRef } from 'react';
import { api, Journal } from '../../../lib/api';
import { fmt } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import styles from './Journals.module.css';

const truncate = (s: string, n = 42) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Journals({ yearFrom, yearTo, onOaError }: Props) {
  // `chartData` is the top journals for the current year range (drives the chart).
  // `journals` drives the table and is re-fetched server-side as the user searches,
  // so journals beyond the default top slice are still reachable.
  const [chartData, setChartData] = useState<Journal[] | null>(null);
  const [journals, setJournals] = useState<Journal[] | null>(null);
  const [search, setSearch] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const requestIdRef = useRef(0);

  useEffect(() => {
    setChartData(null);
    setJournals(null);
    api.journalsTop(search.trim(), yearFrom, yearTo)
      .then(r => { setChartData(r.data); setJournals(r.data); })
      .catch(() => onOaError());
    // Re-run on year change; `search` is intentionally read fresh, not a dep
    // (search edits go through handleSearch's own debounced fetch).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yearFrom, yearTo]);

  const handleSearch = (q: string) => {
    setSearch(q);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      const requestId = ++requestIdRef.current;
      api.journalsTop(q.trim(), yearFrom, yearTo)
        .then(r => { if (requestId === requestIdRef.current) setJournals(r.data); })
        .catch(() => onOaError());
    }, 400);
  };

  const columns: Column<Journal & { __rank: number }>[] = [
    { key: '__rank', label: '#', render: v => <span className="rankBadge">{String(v)}</span> },
    { key: 'name', label: 'Venue' },
    { key: 'count', label: 'Publications', render: v => fmt(Number(v)) },
  ];

  const topN = (chartData ?? []).slice(0, 15);

  return (
    <div className={`${styles.root} fadeInUp`}>
      <ChartCard title="Top 15 Venues by Publications" source="openalex" tall>
        {chartData === null ? (
          <Skeleton height={480} />
        ) : topN.length === 0 ? (
          <p className={styles.emptyMsg}>No venues found.</p>
        ) : (
          <div style={{ height: 480 }}>
            <HorizontalBarChart
              labels={topN.map(j => truncate(j.name))}
              data={topN.map(j => j.count)}
              xFormatter={fmt}
            />
          </div>
        )}
      </ChartCard>

      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>Venue Table</h3>
          <input
            className={styles.searchInput}
            type="search"
            placeholder="Search venues…"
            aria-label="Search venues"
            value={search}
            onChange={e => handleSearch(e.target.value)}
          />
        </div>
        {journals === null
          ? <Skeleton height={300} borderRadius={0} />
          : <DataTable
              columns={columns}
              rows={journals.map((j, i) => ({ ...j, __rank: i + 1 }))}
              emptyMessage={search ? 'No venues match your search.' : 'No venues found.'}
            />
        }
      </div>
    </div>
  );
}
