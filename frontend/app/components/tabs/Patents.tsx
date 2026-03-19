'use client';
import { useEffect, useState, useCallback } from 'react';
import { api, Patent } from '../../../lib/api';
import { fmt, fmtDate, downloadCSV, today } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import StatCard from '../StatCard';
import DataTable, { Column } from '../DataTable';
import Pagination from '../Pagination';
import Skeleton from '../Skeleton';
import BarChart from '../charts/BarChart';
import styles from './Patents.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Patents({ onDimError }: Props) {
  const [byYear, setByYear] = useState<Array<{ year: string; count: number }> | null>(null);
  const [items, setItems] = useState<Patent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [listLoading, setListLoading] = useState(true);

  useEffect(() => {
    api.patentsByYear()
      .then(r => { setByYear(r.data); setTotal(r.data.reduce((s, d) => s + d.count, 0)); })
      .catch(() => onDimError());
  }, []);

  const loadList = useCallback(async (p: number) => {
    setListLoading(true);
    try {
      const res = await api.patentsList(p, 25);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch { onDimError(); }
    finally { setListLoading(false); }
  }, []);

  useEffect(() => { loadList(page); }, [page, loadList]);

  const handleExport = async () => {
    try {
      const res = await api.patentsList(1, 1000);
      downloadCSV(
        `um_research_patents_${today()}.csv`,
        ['Title', 'Filing Date', 'Grant Date'],
        res.data.items.map(p => [p.title, p.filing_date, p.grant_date])
      );
    } catch {}
  };

  const yearTotal = byYear?.reduce((s, d) => s + d.count, 0) ?? 0;

  const columns: Column<Patent>[] = [
    { key: 'title', label: 'Title', render: v => <span style={{ fontWeight: 500 }}>{String(v ?? '—')}</span> },
    { key: 'filing_date', label: 'Filing Date', render: v => fmtDate(String(v ?? '')) },
    { key: 'grant_date', label: 'Grant Date', render: v => fmtDate(String(v ?? '')) },
  ];

  return (
    <div className={`${styles.root} fadeInUp`}>
      <div className={styles.statRow}>
        <StatCard label="Total Patents" value={yearTotal > 0 ? fmt(yearTotal) : undefined} source="dimensions" loading={byYear === null} />
      </div>

      <ChartCard title="Patents Filed per Year" source="dimensions">
        {byYear
          ? <div style={{ height: 280 }}>
              <BarChart
                labels={byYear.map(d => d.year)}
                datasets={[{ label: 'Patents', data: byYear.map(d => d.count), color: '#002147' }]}
              />
            </div>
          : <Skeleton height={280} />
        }
      </ChartCard>

      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>Patent List</h3>
          <button className={styles.csvBtn} onClick={handleExport}>⬇ Download CSV</button>
        </div>
        {listLoading
          ? <Skeleton height={300} borderRadius={0} />
          : <DataTable columns={columns} rows={items} emptyMessage="No patents found." />
        }
        <Pagination page={page} total={total} perPage={25} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
      </div>
    </div>
  );
}
