'use client';
import { useEffect, useState } from 'react';
import { api, CollabInstitution, CollabCountry } from '../../../lib/api';
import { fmt, CHART_COLORS } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import Skeleton from '../Skeleton';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import styles from './Collaborations.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Collaborations({ onOaError }: Props) {
  const [institutions, setInstitutions] = useState<CollabInstitution[] | null>(null);
  const [countries, setCountries] = useState<CollabCountry[] | null>(null);

  useEffect(() => {
    Promise.allSettled([api.collabInstitutions(), api.collabCountries()]).then(([instRes, countryRes]) => {
      if (instRes.status === 'fulfilled') setInstitutions(instRes.value.data);
      else onOaError();
      if (countryRes.status === 'fulfilled') setCountries(countryRes.value.data);
    });
  }, []);

  const truncate = (s: string, n = 42) => s.length > n ? s.slice(0, n - 1) + '…' : s;

  const instLabels = (institutions ?? []).map(d => truncate(d.name));
  const instData   = (institutions ?? []).map(d => d.count);
  const countryTop15 = (countries ?? []).slice(0, 15);

  return (
    <div className={`${styles.root} fadeInUp`}>
      <div className={styles.charts}>
        <ChartCard title="Top 20 Collaborating Institutions" source="openalex" tall>
          {institutions
            ? <div style={{ height: 500 }}>
                <HorizontalBarChart
                  labels={instLabels}
                  data={instData}
                  xFormatter={fmt}
                />
              </div>
            : <Skeleton height={500} />
          }
        </ChartCard>

        <ChartCard title="Top 15 Collaborating Countries" source="openalex" tall>
          {countries
            ? <div style={{ height: 500 }}>
                <HorizontalBarChart
                  labels={countryTop15.map(d => d.country)}
                  data={countryTop15.map(d => d.count)}
                  colors={countryTop15.map((_, i) => CHART_COLORS[i % CHART_COLORS.length])}
                  xFormatter={fmt}
                />
              </div>
            : <Skeleton height={500} />
          }
        </ChartCard>
      </div>

      {/* Country table */}
      {countries && countries.length > 0 && (
        <div className={styles.countryCard}>
          <div className={styles.countryHeader}><h3 className={styles.countryTitle}>All Collaborating Countries</h3></div>
          <div className={styles.countryGrid}>
            {countries.map((c, i) => (
              <div key={c.country_code} className={styles.countryRow}>
                <span className={styles.countryRank}>{i + 1}</span>
                <span className={styles.countryName}>{c.country}</span>
                <span className={styles.countryCode}>{c.country_code}</span>
                <span className={styles.countryCount}>{fmt(c.count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
