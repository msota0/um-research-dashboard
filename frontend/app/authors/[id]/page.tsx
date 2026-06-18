'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, AuthorDetail, AuthorWork, AuthorGrant, AuthorPatent, CitationSourceRow } from '../../../lib/api';
import { fmt, fmtUSD } from '../../../lib/utils';
import Skeleton from '../../components/Skeleton';
import Badge from '../../components/Badge';
import ExpertiseTags, { ExpertiseKeyword } from '../../components/ExpertiseTags';
import styles from './profile.module.css';

export default function AuthorProfilePage() {
  const params = useParams();
  const router = useRouter();
  const id = Array.isArray(params.id) ? params.id[0] : (params.id ?? '');

  const [detail, setDetail] = useState<AuthorDetail | null>(null);
  const [works, setWorks] = useState<AuthorWork[] | null>(null);
  const [expertise, setExpertise] = useState<ExpertiseKeyword[] | null>(null);
  const [grants, setGrants] = useState<AuthorGrant[] | null>(null);
  const [patents, setPatents] = useState<AuthorPatent[] | null>(null);
  const [sources, setSources] = useState<CitationSourceRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);

    (async () => {
      const [detailRes, worksRes, expertiseRes, grantsRes, patentsRes, sourcesRes] =
        await Promise.allSettled([
          api.authorDetail(id),
          api.authorWorks(id),
          api.authorExpertise(id),
          api.authorGrants(id),
          api.authorPatents(id),
          api.authorCitationSources(id),
        ]);
      if (cancelled) return;

      if (detailRes.status === 'fulfilled') setDetail(detailRes.value.data);
      else setNotFound(true);

      if (worksRes.status === 'fulfilled') setWorks(worksRes.value.data);
      if (expertiseRes.status === 'fulfilled') setExpertise(expertiseRes.value.data);
      if (grantsRes.status === 'fulfilled') setGrants(grantsRes.value.data);
      if (patentsRes.status === 'fulfilled') setPatents(patentsRes.value.data);
      if (sourcesRes.status === 'fulfilled') setSources(sourcesRes.value.data);

      setLoading(false);
    })();

    return () => { cancelled = true; };
  }, [id]);

  const googlePatentUrl = (pid: string) => `https://patents.google.com/patent/${pid.replace(/-/g, '')}`;
  const totalFunding = (grants ?? []).reduce((s, g) => s + (g.funding_usd || 0), 0);

  return (
    <div className={styles.page}>
      <nav className={styles.topBar} aria-label="Breadcrumb">
        <button className={styles.backBtn} onClick={() => router.push('/?tab=authors')}>
          <span aria-hidden="true">←</span> Back to Authors
        </button>
        <Link href="/" className={styles.homeLink}>Dashboard</Link>
      </nav>

      <main id="main-content">
      {notFound ? (
        <div className={styles.card}>
          <p className={styles.emptyMsg}>Author not found.</p>
        </div>
      ) : (
        <div className={styles.card}>
          {/* Header */}
          <div className={styles.header}>
            <div>
              <h1 className={styles.name}>{detail?.name ?? (loading ? 'Loading…' : id)}</h1>
              {detail?.department && (
                <p className={styles.dept}><span aria-hidden="true">🏛</span> {detail.department}</p>
              )}
              {detail?.primary_field && (
                <p className={styles.field}>{detail.primary_field}</p>
              )}
              <div className={styles.links}>
                {detail?.orcid && (
                  <a href={detail.orcid} target="_blank" rel="noreferrer" className={styles.extLink}
                     aria-label="ORCID profile (opens in a new tab)">
                    <span aria-hidden="true">🆔</span> ORCID Profile
                  </a>
                )}
                {detail?.scholar_url && (
                  <a href={detail.scholar_url} target="_blank" rel="noreferrer" className={styles.extLink}
                     aria-label="Google Scholar profile (opens in a new tab)">
                    <span aria-hidden="true">🎓</span> Google Scholar
                  </a>
                )}
              </div>
            </div>
            <Badge source="openalex" />
          </div>

          {/* Stats */}
          <div className={styles.stats}>
            <div className={styles.stat}>
              <span className={styles.statVal}>{detail ? fmt(detail.total_publications) : '…'}</span>
              <span className={styles.statLabel}>Total Publications</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statVal}>{detail ? fmt(detail.um_publications) : '…'}</span>
              <span className={styles.statLabel}>UM Publications</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statVal}>{detail ? fmt(detail.cited_by_count) : '…'}</span>
              <span className={styles.statLabel}>Citations</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statVal}>{detail ? detail.h_index : '…'}</span>
              <span className={styles.statLabel}>h-index</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statVal}>{detail ? detail.i10_index : '…'}</span>
              <span className={styles.statLabel}>i10-index</span>
            </div>
          </div>

          {/* Expertise */}
          <h2 className={styles.sectionTitle}>Expertise &amp; Research Keywords</h2>
          <div className={styles.expertiseSection}>
            {loading ? <Skeleton height={80} /> : <ExpertiseTags keywords={expertise ?? []} />}
          </div>

          {/* Works */}
          <h2 className={styles.sectionTitle}>Top Publications</h2>
          {loading ? (
            <div style={{ padding: '0 24px 20px' }}><Skeleton height={180} /></div>
          ) : works && works.length > 0 ? (
            <ul className={styles.worksList}>
              {works.map((w, i) => (
                <li key={i} className={styles.workItem}>
                  <div className={styles.workTitle}>
                    {w.doi ? (
                      <a
                        href={`https://doi.org/${w.doi.replace('https://doi.org/', '')}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {w.title}
                      </a>
                    ) : (
                      w.title
                    )}
                  </div>
                  <div className={styles.workMeta}>{w.year ?? '—'} · {w.citations} citations</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.noWorks}>No works found.</p>
          )}

          {/* Grants (Dimensions) */}
          <h2 className={styles.sectionTitle}>
            Grants {grants && grants.length > 0 && (
              <span className={styles.sectionMeta}>{grants.length} · {fmtUSD(totalFunding)}</span>
            )}
          </h2>
          {loading ? (
            <div style={{ padding: '0 24px 20px' }}><Skeleton height={80} /></div>
          ) : grants && grants.length > 0 ? (
            <ul className={styles.itemList}>
              {grants.map((g, i) => (
                <li key={i} className={styles.item}>
                  <div className={styles.itemTitle}>{g.title || 'Untitled grant'}</div>
                  <div className={styles.itemMeta}>
                    {g.funder ?? '—'}{g.start_year ? ` · ${g.start_year}` : ''}
                    {g.role ? ` · ${g.role}` : ''} · {fmtUSD(g.funding_usd)}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.noWorks}>No grants matched to this author.</p>
          )}

          {/* Patents (Dimensions) */}
          <h2 className={styles.sectionTitle}>
            Patents {patents && patents.length > 0 && (
              <span className={styles.sectionMeta}>{patents.length}</span>
            )}
          </h2>
          {loading ? (
            <div style={{ padding: '0 24px 20px' }}><Skeleton height={80} /></div>
          ) : patents && patents.length > 0 ? (
            <ul className={styles.itemList}>
              {patents.map((p) => (
                <li key={p.id} className={styles.item}>
                  <div className={styles.itemTitle}>
                    <a href={googlePatentUrl(p.id)} target="_blank" rel="noreferrer">
                      {p.title || p.id}
                    </a>
                  </div>
                  <div className={styles.itemMeta}>
                    {p.year ?? '—'}{p.filing_status ? ` · ${p.filing_status}` : ''} · {p.times_cited} citations
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.noWorks}>No patents matched to this author.</p>
          )}

          {/* Top cited sources (OpenAlex) */}
          {sources && sources.length > 0 && (
            <>
              <h2 className={styles.sectionTitle}>
                Top Cited Sources <span className={styles.sectionMeta}>{sources.length}</span>
              </h2>
              <ul className={styles.itemList}>
                {sources.slice(0, 10).map((s, i) => (
                  <li key={i} className={styles.item}>
                    <div className={styles.itemTitle}>{s.source_name}</div>
                    <div className={styles.itemMeta}>
                      {s.publisher || '—'} · {s.citation_count} citations
                      {s.is_oa ? ` · ${s.oa_type || 'open'}` : ''}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      </main>
    </div>
  );
}
