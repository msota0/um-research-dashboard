'use client';
import { useEffect, useState } from 'react';
import { api, OAStatus, OATrendItem } from '../../../lib/api';
import { OA_COLORS, fmt } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import Skeleton from '../Skeleton';
import DonutChart from '../charts/DonutChart';
import LineChart from '../charts/LineChart';
import styles from './OpenAccess.module.css';

interface Props {
  yearFrom: number;
  yearTo: number;
  onDimError: () => void;
  onOaError: () => void;
}

export default function OpenAccess({ onOaError }: Props) {
  const [oaStats, setOaStats] = useState<OAStatus[] | null>(null);
  const [trend, setTrend] = useState<OATrendItem[] | null>(null);

  useEffect(() => {
    Promise.allSettled([api.pubsOpenAccess(), api.oaTrend()]).then(([oaRes, trendRes]) => {
      if (oaRes.status === 'fulfilled') setOaStats(oaRes.value.data);
      else onOaError();
      if (trendRes.status === 'fulfilled') setTrend(trendRes.value.data);
    });
  }, []);

  const total = oaStats?.reduce((s, d) => s + d.count, 0) ?? 0;
  const openCount =
    oaStats?.filter(d => d.oa_status !== 'closed').reduce((s, d) => s + d.count, 0) ?? 0;
  const oaPct = total > 0 ? ((openCount / total) * 100).toFixed(1) : null;

  const donutColors = oaStats?.map(d => OA_COLORS[d.oa_status] ?? '#BDC3C7');
  const donutLabels =
    oaStats?.map(d => d.oa_status.charAt(0).toUpperCase() + d.oa_status.slice(1)) ?? [];

  return (
    <div className={`${styles.root} fadeInUp`}>
      {oaPct && (
        <div className={styles.summaryBanner}>
          <span className={styles.summaryPct}>{oaPct}%</span>
          <span className={styles.summaryText}>
            of University of Mississippi research is openly accessible
            ({fmt(openCount)} of {fmt(total)} publications)
          </span>
        </div>
      )}

      <div className={styles.charts}>
        <ChartCard
          title="Open Access Status Breakdown"
          source="openalex"
          tooltip="Gold = publisher OA journal. Green = repository copy. Hybrid = OA in subscription journal. Bronze = free to read but not licensed. Closed = no open version."
        >
          {oaStats ? (
            <div style={{ height: 280 }}>
              <DonutChart
                labels={donutLabels}
                data={oaStats.map(d => d.count)}
                colors={donutColors}
              />
            </div>
          ) : (
            <Skeleton height={280} />
          )}
        </ChartCard>

        <ChartCard title="OA Percentage by Year (Last 10 Years)" source="openalex">
          {trend ? (
            <div style={{ height: 280 }}>
              <LineChart
                labels={trend.map(d => d.year)}
                datasets={[
                  {
                    label: 'OA %',
                    data: trend.map(d => d.oa_percentage),
                    color: OA_COLORS.green,
                    fill: true,
                  },
                ]}
                yFormatter={v => v + '%'}
                yMax={100}
              />
            </div>
          ) : (
            <Skeleton height={280} />
          )}
        </ChartCard>
      </div>

      {/* OA status legend table */}
      {oaStats && (
        <div className={styles.legendCard}>
          <table className={styles.legendTable}>
            <thead>
              <tr>
                <th>Status</th>
                <th>Count</th>
                <th>% of Total</th>
              </tr>
            </thead>
            <tbody>
              {oaStats.map(d => (
                <tr key={d.oa_status}>
                  <td>
                    <span
                      className="oaBadge"
                      style={{ background: OA_COLORS[d.oa_status] ?? '#BDC3C7' }}
                    >
                      {d.oa_status}
                    </span>
                  </td>
                  <td>{fmt(d.count)}</td>
                  <td>{total > 0 ? ((d.count / total) * 100).toFixed(1) + '%' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
