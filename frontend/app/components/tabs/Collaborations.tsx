// 'use client';
// import { useEffect, useState } from 'react';
// import { api, CollabInstitution, CollabCountry } from '../../../lib/api';
// import { fmt, CHART_COLORS } from '../../../lib/utils';
// import ChartCard from '../ChartCard';
// import Skeleton from '../Skeleton';
// import HorizontalBarChart from '../charts/HorizontalBarChart';
// import styles from './Collaborations.module.css';

// interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

// export default function Collaborations({ onOaError }: Props) {
//   const [institutions, setInstitutions] = useState<CollabInstitution[] | null>(null);
//   const [countries, setCountries] = useState<CollabCountry[] | null>(null);

//   useEffect(() => {
//     Promise.allSettled([api.collabInstitutions(), api.collabCountries()]).then(([instRes, countryRes]) => {
//       if (instRes.status === 'fulfilled') setInstitutions(instRes.value.data);
//       else onOaError();
//       if (countryRes.status === 'fulfilled') setCountries(countryRes.value.data);
//     });
//   }, []);

//   const truncate = (s: string, n = 42) => s.length > n ? s.slice(0, n - 1) + '…' : s;

//   const instLabels = (institutions ?? []).map(d => truncate(d.name));
//   const instData   = (institutions ?? []).map(d => d.count);
//   const countryTop15 = (countries ?? []).slice(0, 15);

//   return (
//     <div className={`${styles.root} fadeInUp`}>
//       <div className={styles.charts}>
//         <ChartCard title="Top 20 Collaborating Institutions" source="openalex" tall>
//           {institutions
//             ? <div style={{ height: 500 }}>
//                 <HorizontalBarChart
//                   labels={instLabels}
//                   data={instData}
//                   xFormatter={fmt}
//                 />
//               </div>
//             : <Skeleton height={500} />
//           }
//         </ChartCard>

//         <ChartCard title="Top 15 Collaborating Countries" source="openalex" tall>
//           {countries
//             ? <div style={{ height: 500 }}>
//                 <HorizontalBarChart
//                   labels={countryTop15.map(d => d.country)}
//                   data={countryTop15.map(d => d.count)}
//                   colors={countryTop15.map((_, i) => CHART_COLORS[i % CHART_COLORS.length])}
//                   xFormatter={fmt}
//                 />
//               </div>
//             : <Skeleton height={500} />
//           }
//         </ChartCard>
//       </div>

//       {/* Country table */}
//       {countries && countries.length > 0 && (
//         <div className={styles.countryCard}>
//           <div className={styles.countryHeader}><h3 className={styles.countryTitle}>All Collaborating Countries</h3></div>
//           <div className={styles.countryGrid}>
//             {countries.map((c, i) => (
//               <div key={c.country_code} className={styles.countryRow}>
//                 <span className={styles.countryRank}>{i + 1}</span>
//                 <span className={styles.countryName}>{c.country}</span>
//                 <span className={styles.countryCode}>{c.country_code}</span>
//                 <span className={styles.countryCount}>{fmt(c.count)}</span>
//               </div>
//             ))}
//           </div>
//         </div>
//       )}
//     </div>
//   );
// }

'use client';
import { useEffect, useRef, useState } from 'react';
import { api, CollabInstitution, CollabCountry } from '../../../lib/api';
import { fmt, CHART_COLORS } from '../../../lib/utils';
import ChartCard from '../ChartCard';
import Skeleton from '../Skeleton';
import HorizontalBarChart from '../charts/HorizontalBarChart';
import styles from './Collaborations.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

/** OpenAlex sometimes returns full URLs like https://openalex.org/countries/US — extract just the code. */
const isoCode = (raw: string): string => raw?.split('/').pop()?.toUpperCase() ?? raw;

/* ─── Country centroid coords (ISO alpha-2) ─────────────────────────────── */
const COUNTRY_COORDS: Record<string, [number, number]> = {
  US:[37.09,-95.71],CA:[56.13,-106.35],GB:[55.38,-3.44],DE:[51.17,10.45],CN:[35.86,104.19],
  AU:[-25.27,133.78],IN:[20.59,78.96],FR:[46.23,2.21],IT:[41.87,12.57],BR:[-14.24,-51.93],
  JP:[36.20,138.25],KR:[35.91,127.77],EG:[26.82,30.80],NL:[52.13,5.29],RU:[61.52,105.32],
  SA:[23.89,45.08],TW:[23.69,120.96],PL:[51.92,19.15],ES:[40.46,-3.75],CH:[46.82,8.23],
  SE:[60.13,18.64],MX:[23.63,-102.55],ZA:[-30.56,22.94],NG:[9.08,8.68],PK:[30.38,69.35],
  AR:[-38.42,-63.62],IE:[53.41,-8.24],UA:[48.38,31.17],VN:[14.06,108.28],CL:[-35.68,-71.54],
  ID:[-0.79,113.92],TR:[38.96,35.24],PT:[39.40,-8.22],IL:[31.05,34.85],CO:[4.57,-74.30],
  NO:[60.47,8.47],FI:[61.92,25.75],NZ:[-40.90,174.89],DK:[56.26,9.50],HU:[47.16,19.50],
  GR:[39.07,21.82],HK:[22.40,114.11],KE:[-0.02,37.91],SG:[1.35,103.82],KZ:[48.02,66.92],
  MY:[4.21,101.98],BD:[23.68,90.36],TH:[15.87,100.99],RO:[45.94,24.97],AT:[47.52,14.55],
  BE:[50.50,4.47],CZ:[49.82,15.47],BG:[42.73,25.49],MA:[31.79,-7.09],AE:[23.42,53.85],
  QA:[25.35,51.18],IR:[32.43,53.69],PH:[12.88,121.77],
};

/* ─── Institution coords (city-level) ───────────────────────────────────── */
const INST_COORDS: Record<string, [number, number]> = {
  'University of Mississippi': [34.36, -89.54],
  'University of Mississippi Medical Center': [32.33, -90.18],
  'Pacific Northwest National Laboratory': [46.34, -119.28],
  'Jackson Memorial Hospital': [25.79, -80.21],
  'Environmental Molecular Sciences Laboratory': [46.34, -119.28],
  'University of California, Riverside': [33.97, -117.33],
  'University of Michigan': [42.28, -83.74],
  'New Mexico State University': [32.28, -106.75],
  'Michigan State University': [42.70, -84.48],
  'Johns Hopkins University': [39.33, -76.62],
  'University of British Columbia': [49.26, -123.25],
  'University of Florida': [29.64, -82.35],
  'Mississippi State University': [33.46, -88.79],
  'University of North Carolina at Chapel Hill': [35.90, -79.05],
  'Stanford University': [37.43, -122.17],
  'Duke University': [36.00, -78.94],
  'Louisiana State University': [30.41, -91.18],
  'University of Minnesota': [44.97, -93.23],
  'Agricultural Research Service': [38.89, -77.04],
  'University of Washington': [47.65, -122.31],
};

/* ─── Bubble Map Component ──────────────────────────────────────────────── */
interface BubbleItem { name: string; code?: string; count: number; }
interface BubbleMapProps {
  items: BubbleItem[];
  coordsLookup: Record<string, [number, number]>;
  keyField: 'code' | 'name';
  bubbleColors?: string[];
}

function BubbleMap({ items, coordsLookup, keyField, bubbleColors }: BubbleMapProps) {
  const svgRef  = useRef<SVGSVGElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; name: string; count: number } | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!svgRef.current || items.length === 0) return;

    Promise.all([
      import('d3-geo'),
      import('topojson-client'),
      fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json').then(r => r.json()),
    ]).then(([d3geo, topojson, world]) => {
      const svg = svgRef.current!;
      const W   = svg.clientWidth || 520;
      const H   = Math.round(W * 0.58);
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
      svg.setAttribute('height', String(H));
      svg.innerHTML = '';

      const countries110 = (topojson as any).feature(world, world.objects.countries);
      const projection   = d3geo.geoNaturalEarth1()
        .scale(W / 5.8)
        .translate([W / 2, H / 1.92]);
      const path = d3geo.geoPath().projection(projection);

      // Base map – light gray land
      const baseG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      for (const feature of countries110.features) {
        const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        p.setAttribute('d', path(feature) ?? '');
        p.setAttribute('fill', '#CFD4DC');
        p.setAttribute('stroke', '#fff');
        p.setAttribute('stroke-width', '0.5');
        baseG.appendChild(p);
      }
      svg.appendChild(baseG);

      // Bubbles
      const maxCount = Math.max(...items.map(i => i.count));
      const maxR     = Math.min(W * 0.036, 20);
      const minR     = 4;
      const scaleR   = (v: number) => minR + (maxR - minR) * Math.sqrt(v / maxCount);

      const FALLBACK_COLORS = [
        '#E05A2B','#2B7BE0','#2BAE5A','#DDB62B','#9B2BE0',
        '#E02B6E','#2BBDE0','#7BE02B','#E0702B','#2B4DE0',
      ];
      const colors = bubbleColors ?? FALLBACK_COLORS;

      // Sort ascending so larger bubbles draw on top
      const sorted = [...items].sort((a, b) => a.count - b.count);

      const bubbleG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      sorted.forEach((item, idx) => {
        const lookupKey = keyField === 'code' ? (item.code ?? '') : item.name;
        const coords    = coordsLookup[lookupKey];
        if (!coords) return;

        const proj = projection([coords[1], coords[0]]);
        if (!proj) return;
        const [cx, cy] = proj;
        const r     = scaleR(item.count);
        const color = colors[idx % colors.length];

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', String(Math.round(cx)));
        circle.setAttribute('cy', String(Math.round(cy)));
        circle.setAttribute('r',  String(r));
        circle.setAttribute('fill', color);
        circle.setAttribute('fill-opacity', '0.85');
        circle.setAttribute('stroke', '#fff');
        circle.setAttribute('stroke-width', '1');
        circle.style.cursor     = 'pointer';
        circle.style.transition = 'r 0.12s, fill-opacity 0.12s';

        circle.addEventListener('mouseenter', (e: MouseEvent) => {
          circle.setAttribute('r', String(r + 2));
          circle.setAttribute('fill-opacity', '1');
          const rect = wrapRef.current!.getBoundingClientRect();
          setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, name: item.name, count: item.count });
        });
        circle.addEventListener('mousemove', (e: MouseEvent) => {
          const rect = wrapRef.current!.getBoundingClientRect();
          setTooltip(prev => prev ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
        });
        circle.addEventListener('mouseleave', () => {
          circle.setAttribute('r', String(r));
          circle.setAttribute('fill-opacity', '0.85');
          setTooltip(null);
        });

        bubbleG.appendChild(circle);
      });
      svg.appendChild(bubbleG);
      setReady(true);
    });
  }, [items]);

  return (
    <div ref={wrapRef} className={styles.mapWrapper}>
      {!ready && <Skeleton height={290} />}
      <svg ref={svgRef} width="100%" style={{ display: ready ? 'block' : 'none' }} />
      {tooltip && (
        <div className={styles.mapTooltip} style={{ left: tooltip.x + 12, top: tooltip.y - 44 }}>
          <strong>{tooltip.name}</strong>
          <span>{fmt(tooltip.count)} papers</span>
        </div>
      )}
    </div>
  );
}

/* ─── Main Component ────────────────────────────────────────────────────── */
export default function Collaborations({ onOaError }: Props) {
  const [institutions, setInstitutions] = useState<CollabInstitution[] | null>(null);
  const [countries,    setCountries   ] = useState<CollabCountry[]     | null>(null);

  useEffect(() => {
    Promise.allSettled([api.collabInstitutions(), api.collabCountries()]).then(([instRes, countryRes]) => {
      if (instRes.status === 'fulfilled') setInstitutions(instRes.value.data);
      else onOaError();
      if (countryRes.status === 'fulfilled') setCountries(countryRes.value.data);
    });
  }, []);

  const truncate      = (s: string, n = 42) => s.length > n ? s.slice(0, n - 1) + '…' : s;
  const instLabels    = (institutions ?? []).map(d => truncate(d.name));
  const instData      = (institutions ?? []).map(d => d.count);
  const countryTop15  = (countries ?? []).slice(0, 15);
  const instItems     = (institutions ?? []).slice(0, 20).map(d => ({ name: d.name, count: d.count }));
  const countryItems  = (countries ?? []).map(d => ({ name: d.country, code: isoCode(d.country_code), count: d.count }));

  return (
    <div className={`${styles.root} fadeInUp`}>

      {/* Two bubble maps side-by-side */}
      <div className={styles.maps}>
        <div className={styles.mapCard}>
          <div className={styles.mapHeader}>
            <h3 className={styles.mapTitle}>Geographic Collaboration Network</h3>
          </div>
          {institutions
            ? <BubbleMap items={instItems} coordsLookup={INST_COORDS} keyField="name" bubbleColors={CHART_COLORS} />
            : <Skeleton height={290} />
          }
        </div>

        <div className={styles.mapCard}>
          <div className={styles.mapHeader}>
            <h3 className={styles.mapTitle}>International Collaboration Network</h3>
          </div>
          {countries
            ? <BubbleMap items={countryItems} coordsLookup={COUNTRY_COORDS} keyField="code" bubbleColors={CHART_COLORS} />
            : <Skeleton height={290} />
          }
        </div>
      </div>

      {/* Bar charts */}
      <div className={styles.charts}>
        <ChartCard title="Top 20 Collaborating Institutions" source="openalex" tall>
          {institutions
            ? <div style={{ height: 500 }}>
                <HorizontalBarChart labels={instLabels} data={instData} xFormatter={fmt} />
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
          <div className={styles.countryHeader}>
            <h3 className={styles.countryTitle}>All Collaborating Countries</h3>
          </div>
          <div className={styles.countryGrid}>
            {countries.map((c, i) => (
              <div key={isoCode(c.country_code)} className={styles.countryRow}>
                <span className={styles.countryRank}>{i + 1}</span>
                <span className={styles.countryName}>{c.country}</span>
                <span className={styles.countryCode}>{isoCode(c.country_code)}</span>
                <span className={styles.countryCount}>{fmt(c.count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}