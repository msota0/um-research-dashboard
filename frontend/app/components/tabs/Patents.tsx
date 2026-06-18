'use client';
import { useEffect, useState } from 'react';
import { api, Patent, PatentsSummary } from '../../../lib/api';
import { fmt } from '../../../lib/utils';
import StatCard from '../StatCard';
import ChartCard from '../ChartCard';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import BarChart from '../charts/BarChart';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import styles from './Patents.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

/** Build a Google Patents URL from a Dimensions patent id like "US-20250294774-A1". */
const googlePatentUrl = (id: string) => `https://patents.google.com/patent/${id.replace(/-/g, '')}`;

const truncate = (s: string, n = 44) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

export default function Patents({ yearFrom, yearTo, onDimError }: Props) {
  const [summary, setSummary] = useState<PatentsSummary | null>(null);
  const [patents, setPatents] = useState<Patent[] | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    setSummary(null);
    setPatents(null);
    Promise.allSettled([
      api.patentsSummary(yearFrom, yearTo),
      api.patentsList(yearFrom, yearTo),
    ]).then(([sumRes, listRes]) => {
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data);
      else onDimError();
      if (listRes.status === 'fulfilled') setPatents(listRes.value.data);
    });
  }, [yearFrom, yearTo]);

  const topInventors = summary?.top_inventors?.slice(0, 15) ?? [];

  const q = search.trim().toLowerCase();
  const filtered = (patents ?? []).filter(p => {
    if (!q) return true;
    return (p.title ?? '').toLowerCase().includes(q) ||
      p.inventors.some(i => i.toLowerCase().includes(q));
  });

  const columns: Column<Patent>[] = [
    {
      key: 'title',
      label: 'Title',
      render: (_, row) => (
        <a href={googlePatentUrl(row.id)} target="_blank" rel="noreferrer">
          {row.title || row.id}
        </a>
      ),
    },
    { key: 'year', label: 'Year', render: v => (v != null ? String(v) : '—') },
    {
      key: 'inventors',
      label: 'Inventors',
      render: (_, row) =>
        row.inventors.length
          ? row.inventors.slice(0, 3).join(', ') + (row.inventors.length > 3 ? ` +${row.inventors.length - 3}` : '')
          : '—',
    },
    { key: 'times_cited', label: 'Citations', render: v => fmt(Number(v)) },
    { key: 'filing_status', label: 'Status', render: v => (v ? String(v) : '—') },
  ];

  return (
    <div className={`${styles.root} fadeInUp`}>
      {/* Stat cards */}
      <div className={styles.statGrid}>
        <StatCard label="Total Patents"    value={summary ? fmt(summary.total_patents) : null}    source="dimensions" loading={!summary} />
        <StatCard label="Patent Citations" value={summary ? fmt(summary.total_cited) : null}       source="dimensions" loading={!summary} />
        <StatCard label="Unique Inventors" value={summary ? fmt(summary.unique_inventors) : null}  source="dimensions" loading={!summary} />
      </div>

      {/* Charts */}
      <ChartCard title="Patents per Year" source="dimensions">
        {summary ? (
          <div style={{ height: 280 }}>
            <BarChart
              labels={summary.by_year.map(d => d.year)}
              datasets={[{ label: 'Patents', data: summary.by_year.map(d => d.count), color: '#002147' }]}
              yFormatter={fmt}
            />
          </div>
        ) : (
          <Skeleton height={280} />
        )}
      </ChartCard>

      <ChartCard title="Top 15 Inventors" source="dimensions" tall>
        {summary ? (
          topInventors.length ? (
            <div style={{ height: 440 }}>
              <HorizontalBarChart
                labels={topInventors.map(d => truncate(d.name))}
                data={topInventors.map(d => d.count)}
                xFormatter={fmt}
              />
            </div>
          ) : (
            <p className={styles.emptyMsg}>No inventor data.</p>
          )
        ) : (
          <Skeleton height={440} />
        )}
      </ChartCard>

      {/* Patent list */}
      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>All Patents</h3>
          <input
            className={styles.searchInput}
            type="search"
            placeholder="Search patents…"
            aria-label="Search patents"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {patents === null
          ? <Skeleton height={300} borderRadius={0} />
          : <DataTable
              columns={columns}
              rows={filtered}
              emptyMessage={search ? 'No patents match your search.' : 'No patents found.'}
            />
        }
      </div>
    </div>
  );
}
