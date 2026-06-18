'use client';
import { useEffect, useState } from 'react';
import { api, Department } from '../../../lib/api';
import { fmt } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import styles from './Fields.module.css';

interface Props {
  yearFrom: number;
  yearTo: number;
  onDimError: () => void;
  onOaError: () => void;
}

type DeptRow = Department & { __rank: number };

export default function Departments({ onDimError }: Props) {
  const [data, setData] = useState<Department[] | null>(null);

  useEffect(() => {
    api.departments()
      .then(r => setData(r.data))
      .catch(() => onDimError());
  }, []);

  const truncate = (s: string, n = 40) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
  const top = (data ?? []).slice(0, 20);

  const columns: Column<DeptRow>[] = [
    { key: '__rank', label: '#', render: v => <span className="rankBadge">{String(v)}</span> },
    { key: 'name', label: 'Department / School' },
    { key: 'publication_count', label: 'Publications', render: v => fmt(Number(v)) },
    { key: 'citation_count', label: 'Citations', render: v => fmt(Number(v)) },
  ];

  const rows: DeptRow[] = (data ?? []).map((d, i) => ({ ...d, __rank: i + 1 }));

  return (
    <div className={`${styles.root} fadeInUp`}>
      <div className={styles.charts}>
        <ChartCard title="Top 20 Departments" source="dimensions" tall>
          {data ? (
            data.length ? (
              <div style={{ height: 480 }}>
                <HorizontalBarChart
                  labels={top.map(d => truncate(d.name))}
                  data={top.map(d => d.publication_count)}
                  xFormatter={fmt}
                />
              </div>
            ) : (
              <p style={{ padding: '2rem', color: '#64748b' }}>
                No department data yet — runs once a valid Dimensions API key is configured.
              </p>
            )
          ) : (
            <Skeleton height={480} />
          )}
        </ChartCard>
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>All Departments</h3>
        </div>
        {data ? (
          <DataTable columns={columns} rows={rows} />
        ) : (
          <Skeleton height={300} borderRadius={0} />
        )}
      </div>
    </div>
  );
}
