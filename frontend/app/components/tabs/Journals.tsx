'use client';
import { useEffect, useState } from 'react';
import { api, Journal } from '../../../lib/api';
import { fmt } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import styles from './Journals.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Journals({ onOaError }: Props) {
  const [journals, setJournals] = useState<Journal[] | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    api.journalsTop()
      .then(r => setJournals(r.data))
      .catch(() => onOaError());
  }, []);

  const truncate = (s: string, n = 42) => s.length > n ? s.slice(0, n - 1) + '…' : s;

  const filtered = (journals ?? []).filter(j =>
    !search || j.name.toLowerCase().includes(search.toLowerCase())
  );

  const columns: Column<Journal & { __rank: number }>[] = [
    { key: '__rank', label: '#', render: v => <span className="rankBadge">{String(v)}</span> },
    { key: 'name', label: 'Journal' },
    { key: 'count', label: 'Publications', render: v => fmt(Number(v)) },
  ];

  return (
    <div className={`${styles.root} fadeInUp`}>
      <ChartCard title="Top 20 Sources by Publication Count" source="openalex" tall>
        {journals
          ? <div style={{ height: 480 }}>
              <HorizontalBarChart
                labels={(journals ?? []).map(d => truncate(d.name))}
                data={(journals ?? []).map(d => d.count)}
                xFormatter={fmt}
              />
            </div>
          : <Skeleton height={480} />
        }
      </ChartCard>

      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>Source Table</h3>
          <input
            className={styles.searchInput}
            type="search"
            placeholder="Search journals…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {journals === null
          ? <Skeleton height={300} borderRadius={0} />
          : <DataTable
              columns={columns}
              rows={filtered.map((j, i) => ({ ...j, __rank: i + 1 }))}
              emptyMessage={search ? 'No journals match your search.' : 'No journals found.'}
            />
        }
      </div>
    </div>
  );
}
