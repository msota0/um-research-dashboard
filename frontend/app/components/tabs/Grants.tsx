'use client';
import { useEffect, useState, useCallback } from 'react';
import { api, Grant, GrantsSummary, GrantYearData } from '../../../lib/api';
import { fmt, fmtUSD, fmtDate, downloadCSV, today } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import StatCard from '../StatCard';
import DataTable, { Column } from '../DataTable';
import Pagination from '../Pagination';
import Skeleton from '../Skeleton';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import LineChart from '../charts/LineChart';
import styles from './Grants.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Grants({ onDimError }: Props) {
  const [summary, setSummary] = useState<GrantsSummary | null>(null);
  const [byYear, setByYear] = useState<GrantYearData[] | null>(null);
  const [items, setItems] = useState<Grant[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([api.grantsSummary(), api.grantsByYear()]).then(([sumRes, yearRes]) => {
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data);
      else onDimError();
      if (yearRes.status === 'fulfilled') setByYear(yearRes.value.data);
      setLoading(false);
    });
  }, []);

  const loadList = useCallback(async (p: number) => {
    setListLoading(true);
    try {
      const res = await api.grantsList(p, 25);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch { onDimError(); }
    finally { setListLoading(false); }
  }, []);

  useEffect(() => { loadList(page); }, [page, loadList]);

  const handleExport = async () => {
    try {
      const res = await api.grantsList(1, 1000);
      downloadCSV(
        `um_research_grants_${today()}.csv`,
        ['Title', 'Funder', 'Funding (USD)', 'Start Date', 'End Date'],
        res.data.items.map(g => [g.title, g.funder_org_name, g.funding_usd ?? '', g.start_date, g.end_date])
      );
    } catch {}
  };

  const columns: Column<Grant>[] = [
    { key: 'title', label: 'Title', render: v => <span style={{ fontWeight: 500 }}>{String(v ?? '—')}</span> },
    { key: 'funder_org_name', label: 'Funder' },
    { key: 'funding_usd', label: 'Amount', render: v => fmtUSD(v as number) },
    { key: 'start_date', label: 'Start', render: v => fmtDate(String(v ?? '')) },
    { key: 'end_date', label: 'End', render: v => fmtDate(String(v ?? '')) },
  ];

  const funderLabels = (summary?.by_funder ?? []).map(f => f.name.length > 30 ? f.name.slice(0, 28) + '…' : f.name);
  const funderData = (summary?.by_funder ?? []).map(f => f.total_usd);

  const yearLabels = (byYear ?? []).map(d => d.year);
  const yearUSD = (byYear ?? []).map(d => d.total_usd);

  return (
    <div className={`${styles.root} fadeInUp`}>
      {/* Stat cards */}
      <div className={styles.statGrid}>
        <StatCard label="Total Grants" value={summary ? fmt(summary.total_grants) : undefined} source="dimensions" loading={loading} />
        <StatCard label="Total Funding" value={summary ? fmtUSD(summary.total_funding_usd) : undefined} source="dimensions" loading={loading} />
        <StatCard
          label="Top Funder"
          value={summary?.by_funder?.[0]?.name ?? undefined}
          sub={summary?.by_funder?.[0] ? fmtUSD(summary.by_funder[0].total_usd) : undefined}
          source="dimensions"
          loading={loading}
        />
      </div>

      {/* Charts */}
      <div className={styles.charts}>
        <ChartCard title="Top 10 Funders by Total USD" source="dimensions" tall>
          {summary
            ? <div style={{ height: 360 }}>
                <HorizontalBarChart
                  labels={funderLabels}
                  data={funderData}
                  xFormatter={fmtUSD}
                />
              </div>
            : <Skeleton height={360} />
          }
        </ChartCard>

        <ChartCard title="Grant Funding by Year" source="dimensions">
          {byYear
            ? <div style={{ height: 280 }}>
                <LineChart
                  labels={yearLabels}
                  datasets={[{ label: 'Total Funding', data: yearUSD, color: '#002147', fill: true }]}
                  yFormatter={fmtUSD}
                />
              </div>
            : <Skeleton height={280} />
          }
        </ChartCard>
      </div>

      {/* List */}
      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>Grant List</h3>
          <button className={styles.csvBtn} onClick={handleExport}>⬇ Download CSV</button>
        </div>
        {listLoading
          ? <Skeleton height={300} borderRadius={0} />
          : <DataTable columns={columns} rows={items} emptyMessage="No grants found (Dimensions AI may be unavailable)." />
        }
        <Pagination page={page} total={total} perPage={25} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
      </div>
    </div>
  );
}
