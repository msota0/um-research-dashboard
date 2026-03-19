'use client';
import { useEffect, useState, useCallback, useRef } from 'react';
import { api, Author, AuthorWork } from '../../../lib/api';
import { fmt } from '../../../lib/utils';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import Badge from '../Badge';
import ExpertiseTags, { ExpertiseKeyword } from '../ExpertiseTags';
import styles from './Authors.module.css';

interface Props { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void; }

export default function Authors({ onOaError }: Props) {
  const [authors, setAuthors] = useState<Author[] | null>(null);
  const [search, setSearch] = useState('');
  const [modalAuthor, setModalAuthor] = useState<Author | null>(null);
  const [modalWorks, setModalWorks] = useState<AuthorWork[] | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [expertiseKeywords, setExpertiseKeywords] = useState<ExpertiseKeyword[] | null>(null);
  const [expertiseLoading, setExpertiseLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const loadAuthors = useCallback(async (q = '') => {
    try {
      const res = await api.authorsTop(q);
      setAuthors(res.data);
    } catch { onOaError(); }
  }, [onOaError]);

  useEffect(() => { loadAuthors(); }, [loadAuthors]);

  const handleSearch = (q: string) => {
    setSearch(q);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => loadAuthors(q), 400);
  };

  const openModal = async (author: Author) => {
    setModalAuthor(author);
    setModalWorks(null);
    setExpertiseKeywords(null);
    setModalLoading(true);
    setExpertiseLoading(true);

    const [worksRes, expertiseRes] = await Promise.allSettled([
      api.authorWorks(author.id),
      api.authorExpertise(author.id, author.orcid),
    ]);

    if (worksRes.status === 'fulfilled') setModalWorks(worksRes.value.data);
    if (expertiseRes.status === 'fulfilled') setExpertiseKeywords(expertiseRes.value.data);

    setModalLoading(false);
    setExpertiseLoading(false);
  };

  const columns: Column<Author & { __rank: number }>[] = [
    { key: '__rank', label: '#', render: v => <span className="rankBadge">{String(v)}</span> },
    { key: 'name', label: 'Name' },
    { key: 'works_count', label: 'Publications', render: v => fmt(Number(v)) },
    { key: 'cited_by_count', label: 'Citations', render: v => fmt(Number(v)) },
    { key: 'h_index', label: 'h-index' },
    {
      key: 'orcid', label: 'ORCID',
      render: v => v
        ? <a href={String(v)} target="_blank" rel="noreferrer" className={styles.orcidLink} onClick={e => e.stopPropagation()}>🆔</a>
        : '—',
    },
  ];

  const rows = (authors ?? []).map((a, i) => ({ ...a, __rank: i + 1 }));

  return (
    <div className={`${styles.root} fadeInUp`}>
      <div className={styles.toolbar}>
        <h3 className={styles.heading}>Top 25 Authors</h3>
        <div className={styles.toolbarRight}>
          <input
            className={styles.searchInput}
            type="search"
            placeholder="Search authors…"
            value={search}
            onChange={e => handleSearch(e.target.value)}
          />
          <Badge source="openalex" />
        </div>
      </div>

      {authors === null
        ? <Skeleton height={400} />
        : <DataTable
            columns={columns}
            rows={rows}
            onRowClick={row => openModal(row as Author & { __rank: number })}
          />
      }

      {/* ── Author detail modal ── */}
      {modalAuthor && (
        <div className={styles.modalOverlay} onClick={() => setModalAuthor(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <h3 className={styles.modalTitle}>{modalAuthor.name}</h3>
                {modalAuthor.orcid && (
                  <a
                    href={modalAuthor.orcid}
                    target="_blank"
                    rel="noreferrer"
                    className={styles.orcidModalLink}
                    onClick={e => e.stopPropagation()}
                  >
                    🆔 ORCID Profile
                  </a>
                )}
              </div>
              <button className={styles.modalClose} onClick={() => setModalAuthor(null)}>✕</button>
            </div>

            {/* Stats row */}
            <div className={styles.modalStats}>
              <div className={styles.modalStat}>
                <span className={styles.modalStatVal}>{fmt(modalAuthor.works_count)}</span>
                <span className={styles.modalStatLabel}>Publications</span>
              </div>
              <div className={styles.modalStat}>
                <span className={styles.modalStatVal}>{fmt(modalAuthor.cited_by_count)}</span>
                <span className={styles.modalStatLabel}>Citations</span>
              </div>
              <div className={styles.modalStat}>
                <span className={styles.modalStatVal}>{modalAuthor.h_index ?? '—'}</span>
                <span className={styles.modalStatLabel}>h-index</span>
              </div>
            </div>

            {/* Expertise keywords */}
            <h4 className={styles.modalSectionTitle}>Expertise &amp; Research Keywords</h4>
            <div className={styles.expertiseSection}>
              {expertiseLoading
                ? <Skeleton height={80} />
                : <ExpertiseTags keywords={expertiseKeywords ?? []} />
              }
            </div>

            {/* Top publications */}
            <h4 className={styles.modalSectionTitle}>Top Publications</h4>
            {modalLoading
              ? <Skeleton height={180} />
              : modalWorks && modalWorks.length > 0
                ? <ul className={styles.worksList}>
                    {modalWorks.map((w, i) => (
                      <li key={i} className={styles.workItem}>
                        <div className={styles.workTitle}>
                          {w.doi
                            ? <a
                                href={`https://doi.org/${w.doi.replace('https://doi.org/', '')}`}
                                target="_blank"
                                rel="noreferrer"
                              >{w.title}</a>
                            : w.title
                          }
                        </div>
                        <div className={styles.workMeta}>{w.year ?? '—'} · {w.citations} citations</div>
                      </li>
                    ))}
                  </ul>
                : <p className={styles.noWorks}>No works found.</p>
            }
          </div>
        </div>
      )}
    </div>
  );
}
