'use client';
import Badge from './Badge';
import styles from './StatCard.module.css';
import SparklineChart from './charts/SparklineChart';

type Source = 'openalex' | 'dimensions' | 'both';

interface Props {
  label: string;
  value?: string | number | null;
  sub?: string;
  source: Source;
  sparkData?: Array<{ year: number; count: number }>;
  loading?: boolean;
}

export default function StatCard({ label, value, sub, source, sparkData, loading }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.badgeWrap}><Badge source={source} /></div>
      <div className={styles.label}>{label}</div>
      {loading || value == null ? (
        <div className={styles.skeleton} />
      ) : (
        <div className={styles.value}>{value}</div>
      )}
      {sub && <div className={styles.sub}>{sub}</div>}
      {sparkData && sparkData.length > 0 && (
        <div className={styles.spark}>
          <SparklineChart data={sparkData} color={source === 'dimensions' ? '#002147' : '#CE1126'} />
        </div>
      )}
    </div>
  );
}
