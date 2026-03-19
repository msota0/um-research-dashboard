'use client';
import { useEffect, useState, useCallback } from 'react';
import { api, Publication, PubsByYearData, TypeCount } from '../../../lib/api';
import { fmt, oaClass, downloadCSV, today } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import DataTable, { Column } from '../DataTable';
import Pagination from '../Pagination';
import Skeleton from '../Skeleton';
import BarChart from '../charts/BarChart';
import styles from './Publications.module.css';

interface Props {
  yearFrom: number;
  yearTo: number;
  onDimError: () => void;
  onOaError: () => void;
}

export default function Publications({ yearFrom, yearTo, onOaError }: Props) {
  const [byYear, setByYear] = useState<PubsByYearData | null>(null);
  const [byType, setByType] = useState<TypeCount[] | null>(null);
  const [items, setItems] = useState<Publication[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState('');
  const [showDim, setShowDim] = useState(false);
  const [loadingYear, setLoadingYear] = useState(true);
  const [loadingList, setLoadingList] = useState(true);

  useEffect(() => {
    setLoadingYear(true);
    Promise.allSettled([api.pubsByYear(yearFrom, yearTo), api.pubsByType()]).then(([yearRes, typeRes]) => {
      if (yearRes.status === 'fulfilled') setByYear(yearRes.value.data);
      else onOaError();
      if (typeRes.status === 'fulfilled') setByType(typeRes.value.data);
      setLoadingYear(false);
    });
  }, [yearFrom, yearTo]);

  const loadList = useCallback(async (p: number, type: string) => {
    setLoadingList(true);
    try {
      const res = await api.pubsList(p, 25, type, yearFrom, yearTo);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch {
      onOaError();
    } finally {
      setLoadingList(false);
    }
  }, [yearFrom, yearTo]);

  useEffect(() => { loadList(page, filterType); }, [page, filterType, loadList]);

  const handleExport = async () => {
    try {
      const res = await api.pubsList(1, 1000, filterType, yearFrom, yearTo);
      downloadCSV(
        `um_research_publications_${today()}.csv`,
        ['Title', 'DOI', 'Year', 'Type', 'OA Status'],
        res.data.items.map(p => [p.title, p.doi ?? '', p.year ?? '', p.type ?? '', p.oa_status ?? ''])
      );
    } catch {}
  };

  const oaData = byYear?.openalex ?? [];
  const dimData = byYear?.dimensions ?? [];

  const barDatasets = [
    { label: 'OpenAlex', data: oaData.map(d => d.count), color: '#CE1126' },
    ...(showDim && dimData.length > 0
      ? [{ label: 'Dimensions', data: dimData.map(d => d.count), color: '#002147', type: 'line' as const }]
      : []),
  ];

  const columns: Column<Publication>[] = [
    {
      key: 'title',
      label: 'Title',
      render: (_, row) =>
        row.doi
          ? (
            <a
              href={`https://doi.org/${row.doi.replace('https://doi.org/', '')}`}
              target="_blank"
              rel="noreferrer"
            >
              {row.title || '—'}
            </a>
          )
          : (row.title || '—'),
    },
    { key: 'year', label: 'Year' },
    { key: 'type', label: 'Type', render: v => (v as string) || '—' },
    {
      key: 'oa_status',
      label: 'OA Status',
      render: v => (
        <span className={oaClass(String(v ?? 'unknown'))}>{String(v ?? 'unknown')}</span>
      ),
    },
  ];

  return (
    <div className={`${styles.root} fadeInUp`}>
      {/* Publications per year chart */}
      <ChartCard
        title="Publications per Year"
        source="both"
        actions={
          <button className={styles.toggleBtn} onClick={() => setShowDim(s => !s)}>
            {showDim ? 'Hide' : 'Show'} Dimensions
          </button>
        }
        tooltip="Bar = OpenAlex count. Line = Dimensions AI count (when toggled)."
      >
        {loadingYear ? (
          <Skeleton height={280} />
        ) : (
          <div style={{ height: 280 }}>
            <BarChart
              labels={oaData.map(d => d.year)}
              datasets={barDatasets}
              yFormatter={fmt}
              showLegend={showDim}
            />
          </div>
        )}
      </ChartCard>

      {/* Filters + type chart */}
      <div className={styles.row}>
        <div className={styles.filterBar}>
          <label className={styles.filterLabel}>Type:</label>
          <select
            className={styles.select}
            value={filterType}
            onChange={e => {
              setPage(1);
              setFilterType(e.target.value);
            }}
          >
            <option value="">All Types</option>
            <option value="article">Article</option>
            <option value="book">Book</option>
            <option value="book-chapter">Book Chapter</option>
            <option value="dataset">Dataset</option>
            <option value="preprint">Preprint</option>
          </select>
        </div>

        <ChartCard title="By Publication Type" source="openalex">
          {byType ? (
            <div style={{ height: 220 }}>
              <BarChart
                labels={byType.map(d => d.type)}
                datasets={[{ label: 'Count', data: byType.map(d => d.count), color: '#002147' }]}
                yFormatter={fmt}
              />
            </div>
          ) : (
            <Skeleton height={220} />
          )}
        </ChartCard>
      </div>

      {/* Publication list */}
      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h3 className={styles.tableTitle}>Publication List</h3>
          <button className={styles.csvBtn} onClick={handleExport}>⬇ Download CSV</button>
        </div>
        {loadingList ? (
          <Skeleton height={300} borderRadius={0} />
        ) : (
          <DataTable
            columns={columns}
            rows={items}
            emptyMessage="No publications found."
          />
        )}
        <Pagination
          page={page}
          total={total}
          perPage={25}
          onPrev={() => setPage(p => p - 1)}
          onNext={() => setPage(p => p + 1)}
        />
      </div>
    </div>
  );
}
