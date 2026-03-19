'use client';
import { useEffect, useState } from 'react';
import { api, FieldCount } from '../../../lib/api';
import { fmt, CHART_COLORS } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import DonutChart from '../charts/DonutChart';
import styles from './Fields.module.css';

interface Props {
  yearFrom: number;
  yearTo: number;
  onDimError: () => void;
  onOaError: () => void;
}

type FieldRow = FieldCount & { __rank: number; __pct: string };

export default function Fields({ onOaError }: Props) {
  const [data, setData] = useState<FieldCount[] | null>(null);

  useEffect(() => {
    api.pubsByField()
      .then(r => setData(r.data))
      .catch(() => onOaError());
  }, []);

  const truncate = (s: string, n = 38) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
  const total = data?.reduce((s, d) => s + d.count, 0) ?? 0;

  const columns: Column<FieldRow>[] = [
    {
      key: '__rank',
      label: '#',
      render: v => <span className="rankBadge">{String(v)}</span>,
    },
    { key: 'field_name', label: 'Field' },
    { key: 'count', label: 'Publications', render: v => fmt(Number(v)) },
    { key: '__pct', label: '% of Total' },
  ];

  const rows: FieldRow[] = (data ?? []).map((d, i) => ({
    ...d,
    __rank: i + 1,
    __pct: total > 0 ? ((d.count / total) * 100).toFixed(1) + '%' : '—',
  }));

  return (
    <div className={`${styles.root} fadeInUp`}>
      <div className={styles.charts}>
        <ChartCard title="Top 20 Research Fields" source="openalex" tall>
          {data ? (
            <div style={{ height: 480 }}>
              <HorizontalBarChart
                labels={data.map(d => truncate(d.field_name))}
                data={data.map(d => d.count)}
                xFormatter={fmt}
              />
            </div>
          ) : (
            <Skeleton height={480} />
          )}
        </ChartCard>

        <ChartCard title="Field Distribution (Top 8)" source="openalex">
          {data ? (
            <div style={{ height: 280 }}>
              <DonutChart
                labels={data.slice(0, 8).map(d => truncate(d.field_name, 28))}
                data={data.slice(0, 8).map(d => d.count)}
                colors={CHART_COLORS.slice(0, 8)}
              />
            </div>
          ) : (
            <Skeleton height={280} />
          )}
        </ChartCard>
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>All Fields</h3>
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
