'use client';
import { useEffect, useState } from 'react';
import { api, InstitutionOverview, GrantsSummary, PubsByYearData, OAStatus } from '../../../lib/api';
import { fmt, fmtUSD, fmtTs } from '../../../lib/utils';
import StatCard from '../StatCard';
import ErrorBanner from '../ErrorBanner';
import styles from './Overview.module.css';

interface Props {
  yearFrom: number;
  yearTo: number;
  onDimError: () => void;
  onOaError: () => void;
}

export default function Overview({ yearFrom, yearTo, onDimError, onOaError }: Props) {
  const [overview, setOverview] = useState<InstitutionOverview | null>(null);
  const [grants, setGrants] = useState<GrantsSummary | null>(null);
  const [oaData, setOaData] = useState<OAStatus[] | null>(null);
  const [pubsData, setPubsData] = useState<PubsByYearData | null>(null);
  const [oaTs, setOaTs] = useState('');
  const [dimTs, setDimTs] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);

      const [overviewRes, grantsRes, oaRes, pubsYearRes] = await Promise.allSettled([
        api.institutionOverview(),
        api.grantsSummary(),
        api.pubsOpenAccess(),
        api.pubsByYear(yearFrom, yearTo),
      ]);

      if (cancelled) return;

      if (overviewRes.status === 'fulfilled') {
        setOverview(overviewRes.value.data);
        setOaTs(fmtTs(overviewRes.value.fetched_at));
      } else {
        onOaError();
      }

      if (grantsRes.status === 'fulfilled') {
        setGrants(grantsRes.value.data);
        setDimTs(fmtTs(grantsRes.value.fetched_at));
      } else {
        onDimError();
      }

      if (oaRes.status === 'fulfilled') setOaData(oaRes.value.data);
      if (pubsYearRes.status === 'fulfilled') setPubsData(pubsYearRes.value.data);

      setLoading(false);
    };

    load();
    return () => { cancelled = true; };
  }, [yearFrom, yearTo]);

  const oaPct = (() => {
    if (!oaData) return null;
    const total = oaData.reduce((s, d) => s + d.count, 0);
    const open = oaData.filter(d => d.oa_status !== 'closed').reduce((s, d) => s + d.count, 0);
    return total > 0 ? ((open / total) * 100).toFixed(1) + '%' : null;
  })();

  const sparkData = overview
    ? [...(overview.counts_by_year ?? [])].slice(0, 5).reverse().map(r => ({ year: r.year, count: r.works_count }))
    : [];

  const oaTotalPubs = pubsData?.openalex?.reduce((s, d) => s + d.count, 0) ?? 0;
  const dimTotalPubs = pubsData?.dimensions?.reduce((s, d) => s + d.count, 0) ?? 0;

  return (
    <div className={`${styles.root} fadeInUp`}>
      {/* Stat cards */}
      <div className={styles.grid}>
        <StatCard
          label="Total Publications"
          value={overview ? fmt(overview.works_count) : undefined}
          source="openalex"
          sparkData={sparkData}
          loading={loading}
        />
        <StatCard
          label="Total Citations"
          value={overview ? fmt(overview.cited_by_count) : undefined}
          source="openalex"
          loading={loading}
        />
        <StatCard
          label="h-index"
          value={overview?.h_index ?? undefined}
          sub={overview ? `i10-index: ${fmt(overview.i10_index)}` : undefined}
          source="openalex"
          loading={loading}
        />
        <StatCard
          label="Open Access %"
          value={oaPct ?? undefined}
          sub="of all publications"
          source="openalex"
          loading={loading || oaData === null}
        />
        <StatCard
          label="Total Grants"
          value={grants ? fmt(grants.total_grants) : undefined}
          sub={grants?.by_funder?.[0] ? `Top: ${grants.by_funder[0].name}` : undefined}
          source="dimensions"
          loading={loading || grants === null}
        />
        <StatCard
          label="Total Grant Funding"
          value={grants ? fmtUSD(grants.total_funding_usd) : undefined}
          source="dimensions"
          loading={loading || grants === null}
        />
      </div>

      {/* Data sources row */}
      <div className={styles.sources}>
        <div className={styles.sourceChip}>
          <span className={styles.sourceDot} style={{ background: 'var(--badge-openalex)' }} />
          <span className={styles.sourceLabel}>OpenAlex</span>
          <span className={styles.sourceTs}>{oaTs || 'Loading…'}</span>
        </div>
        <div className={styles.sourceChip}>
          <span className={styles.sourceDot} style={{ background: 'var(--badge-dimensions)' }} />
          <span className={styles.sourceLabel}>Dimensions AI</span>
          <span className={styles.sourceTs}>{dimTs || 'Loading…'}</span>
        </div>
      </div>

      {/* Publication count reconciliation note */}
      {dimTotalPubs > 0 && oaTotalPubs > 0 && (
        <div className={styles.infoBox}>
          <span className={styles.infoIcon}>ℹ</span>
          <span>
            <strong>Publication count note:</strong>{' '}
            OpenAlex reports <strong>{fmt(oaTotalPubs)}</strong> publications; Dimensions reports <strong>{fmt(dimTotalPubs)}</strong>.
            Counts differ because each system uses different coverage and disambiguation methods — both are valid estimates.
          </span>
        </div>
      )}
    </div>
  );
}
