'use client';
/**
 * CitationSources.tsx — Two-panel split layout
 *
 * LEFT  panel: scrollable author list
 * RIGHT panel: sticky sources panel for the selected author
 *
 * Clicking an author highlights them on the left and immediately
 * populates the right panel — no inline expansion, no page scroll needed.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, Author } from '../../../lib/api';
import { fmt, oaClass } from '../../../lib/utils';
import Skeleton from '../Skeleton';
import Badge from '../Badge';
import styles from './CitationSources.module.css';

interface CitationSourceRow {
  source_name:    string;
  publisher:      string;
  citation_count: number;
  is_oa:          boolean;
  oa_type:        string;
}

interface Props {
  yearFrom:   number;
  yearTo:     number;
  onDimError: () => void;
  onOaError:  () => void;
}

const PAGE_SIZE = 25;
const API_BASE  = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:5000';

async function fetchCitationSources(authorId: string): Promise<CitationSourceRow[]> {
  const res = await fetch(`${API_BASE}/api/authors/${authorId}/citation-sources`, { cache: 'no-store' });
  if (!res.ok) throw new Error(res.statusText);
  const json = await res.json();
  return json.data ?? [];
}

export default function CitationSources({ onOaError, onDimError }: Props) {
  // ── author list
  const [authors,        setAuthors]        = useState<Author[]>([]);
  const [total,          setTotal]          = useState<number | null>(null);
  const [page,           setPage]           = useState(1);
  const [loadingAuthors, setLoadingAuthors] = useState(true);
  const [loadingMore,    setLoadingMore]    = useState(false);
  const [search,         setSearch]         = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // ── right panel
  const [selectedAuthor,   setSelectedAuthor]   = useState<Author | null>(null);
  const [sources,          setSources]          = useState<CitationSourceRow[]>([]);
  const [loadingSources,   setLoadingSources]   = useState(false);
  const [sourcesMap,       setSourcesMap]       = useState<Record<string, CitationSourceRow[]>>({});
  const [sourceSearch,     setSourceSearch]     = useState('');
  const [sourceFilter,     setSourceFilter]     = useState<'all' | 'oa' | 'closed'>('all');

  // ── load authors
  const loadPage = useCallback(async (pageNum: number, q: string, replace = false) => {
    try {
      const res  = await api.authorsTop(q, pageNum, PAGE_SIZE);
      const items: Author[] = res.data?.items ?? res.data ?? [];
      const count: number   = res.data?.total ?? items.length;
      setAuthors(prev => (replace || pageNum === 1) ? items : [...prev, ...items]);
      setTotal(count);
      setPage(pageNum);
    } catch {
      onOaError();
    }
  }, [onOaError]);

  useEffect(() => {
    loadPage(1, '').finally(() => setLoadingAuthors(false));
  }, [loadPage]);

  const handleSearch = (q: string) => {
    setSearch(q);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setLoadingAuthors(true);
      loadPage(1, q, true).finally(() => setLoadingAuthors(false));
    }, 400);
  };

  const handleLoadMore = async () => {
    setLoadingMore(true);
    await loadPage(page + 1, search);
    setLoadingMore(false);
  };

  // ── select author → load sources into right panel
  const handleSelectAuthor = async (author: Author) => {
    // Deselect if clicking the same author
    if (selectedAuthor?.id === author.id) {
      setSelectedAuthor(null);
      setSources([]);
      return;
    }

    setSelectedAuthor(author);
    setSourceSearch('');
    setSourceFilter('all');

    // Already fetched?
    if (sourcesMap[author.id] !== undefined) {
      setSources(sourcesMap[author.id]);
      return;
    }

    setLoadingSources(true);
    try {
      const data = await fetchCitationSources(author.id);
      setSourcesMap(prev => ({ ...prev, [author.id]: data }));
      setSources(data);
    } catch {
      onDimError();
      setSourcesMap(prev => ({ ...prev, [author.id]: [] }));
      setSources([]);
    } finally {
      setLoadingSources(false);
    }
  };

  // ── derived
  const visibleSources = sources.filter(s => {
    const matchText = !sourceSearch ||
      s.source_name.toLowerCase().includes(sourceSearch.toLowerCase()) ||
      s.publisher.toLowerCase().includes(sourceSearch.toLowerCase());
    const matchOA =
      sourceFilter === 'all'   ? true :
      sourceFilter === 'oa'    ? s.is_oa :
      /* closed */               !s.is_oa;
    return matchText && matchOA;
  });

  const totalCitations = sources.reduce((n, s) => n + s.citation_count, 0);
  const oaCount        = sources.filter(s => s.is_oa).length;
  const hasMore        = total !== null && authors.length < total;

  return (
    <div className={styles.root}>

      {/* ══ LEFT: author list ══════════════════════════════════════════════ */}
      <div className={styles.leftPanel}>

        {/* toolbar */}
        <div className={styles.leftToolbar}>
          <div>
            <h3 className={styles.heading}>
              Citation Sources
              {total !== null && <span className={styles.headingCount}> — {fmt(total)} authors</span>}
            </h3>
            <p className={styles.subheading}>
              Select an author to see which sources they cite and whether those sources are open access.
            </p>
          </div>
          <div className={styles.toolbarRow}>
            <input
              className={styles.searchInput}
              type="search"
              placeholder="Search authors…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
            />
            <Badge source="both" />
          </div>
        </div>

        {/* author list */}
        {loadingAuthors ? (
          <Skeleton height={400} />
        ) : (
          <div className={styles.authorList}>
            {authors.map(author => {
              const isSelected = selectedAuthor?.id === author.id;
              const cached     = sourcesMap[author.id];
              return (
                <button
                  key={author.id}
                  className={`${styles.authorRow} ${isSelected ? styles.authorRowSelected : ''}`}
                  onClick={() => handleSelectAuthor(author)}
                >
                  <div className={styles.authorMeta}>
                    <span className={styles.authorName}>{author.name}</span>
                    <span className={styles.authorStats}>
                      {fmt(author.works_count)} pubs
                      &ensp;·&ensp;
                      {fmt(author.cited_by_count)} citations
                      &ensp;·&ensp;
                      h-index {author.h_index ?? '—'}
                    </span>
                  </div>
                  {cached && cached.length > 0 && (
                    <span className={styles.cachedPill}>{cached.length} sources</span>
                  )}
                  <span className={styles.arrow}>{isSelected ? '▶' : '›'}</span>
                </button>
              );
            })}

            {hasMore && (
              <div className={styles.loadMoreRow}>
                {loadingMore
                  ? <Skeleton height={36} />
                  : <button className={styles.loadMoreBtn} onClick={handleLoadMore}>
                      Show more
                      <span className={styles.loadMoreMeta}> ({authors.length} of {fmt(total!)})</span>
                    </button>
                }
              </div>
            )}
          </div>
        )}
      </div>

      {/* ══ RIGHT: sources panel ═══════════════════════════════════════════ */}
      <div className={styles.rightPanel}>
        {!selectedAuthor ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>←</div>
            <p className={styles.emptyTitle}>Select an author</p>
            <p className={styles.emptySubtitle}>
              Click any author on the left to see which journals and publishers
              they cite and whether those sources are open access.
            </p>
          </div>
        ) : (
          <div className={styles.sourcesContent}>

            {/* right panel header */}
            <div className={styles.rightHeader}>
              <div>
                <h4 className={styles.rightAuthorName}>{selectedAuthor.name}</h4>
                <span className={styles.rightAuthorStats}>
                  {fmt(selectedAuthor.works_count)} pubs
                  &ensp;·&ensp;
                  {fmt(selectedAuthor.cited_by_count)} citations
                  &ensp;·&ensp;
                  h-index {selectedAuthor.h_index ?? '—'}
                </span>
              </div>
              <button className={styles.closeBtn} onClick={() => { setSelectedAuthor(null); setSources([]); }}>✕</button>
            </div>

            {loadingSources ? (
              <div className={styles.loadingWrap}>
                <Skeleton height={80} />
                <Skeleton height={300} />
              </div>
            ) : sources.length === 0 ? (
              <p className={styles.emptyMsg}>No citation source data found in Dimensions AI.</p>
            ) : (
              <>
                {/* summary cards */}
                <div className={styles.summaryBar}>
                  <div className={styles.summaryCard}>
                    <span className={styles.summaryVal}>{fmt(totalCitations)}</span>
                    <span className={styles.summaryLabel}>References made</span>
                  </div>
                  <div className={styles.summaryCard}>
                    <span className={styles.summaryVal}>{sources.length}</span>
                    <span className={styles.summaryLabel}>Unique sources</span>
                  </div>
                  <div className={styles.summaryCard}>
                    <span className={styles.summaryVal}>{oaCount}</span>
                    <span className={styles.summaryLabel}>OA sources</span>
                  </div>
                  <div className={styles.summaryCard}>
                    <span className={`${styles.summaryVal} ${styles.summaryPct}`}>
                      {sources.length > 0 ? Math.round((oaCount / sources.length) * 100) : 0}%
                    </span>
                    <span className={styles.summaryLabel}>OA rate</span>
                  </div>
                </div>

                {/* filter controls */}
                <div className={styles.filterRow}>
                  <input
                    className={styles.sourceSearch}
                    type="search"
                    placeholder="Filter sources…"
                    value={sourceSearch}
                    onChange={e => setSourceSearch(e.target.value)}
                  />
                  <div className={styles.filterPills}>
                    {(['all', 'oa', 'closed'] as const).map(f => (
                      <button
                        key={f}
                        className={`${styles.filterPill} ${sourceFilter === f ? styles.filterPillActive : ''}`}
                        onClick={() => setSourceFilter(f)}
                      >
                        {f === 'all' ? 'All' : f === 'oa' ? 'Open Access' : 'Closed'}
                      </button>
                    ))}
                  </div>
                  <span className={styles.sourceCount}>{visibleSources.length} of {sources.length}</span>
                </div>

                {/* sources table */}
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th className={styles.thRank}>#</th>
                        <th className={styles.thSource}>Source</th>
                        <th className={styles.thCount}>Times cited</th>
                        <th className={styles.thOA}>OA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleSources.map((s, idx) => (
                        <tr key={s.source_name} className={styles.tr}>
                          <td className={styles.tdRank}>
                            <span className="rankBadge">{idx + 1}</span>
                          </td>
                          <td className={styles.tdSource}>
                            <span className={styles.sourceName}>{s.source_name}</span>
                            {s.publisher && (
                              <span className={styles.sourcePublisher}>{s.publisher}</span>
                            )}
                          </td>
                          <td className={styles.tdCount}>
                            <div className={styles.countBar}>
                              <div
                                className={styles.countBarFill}
                                style={{
                                  width: `${Math.min(160, (s.citation_count / (visibleSources[0]?.citation_count || 1)) * 160)}px`,
                                  background: s.is_oa ? 'var(--oa-green)' : 'var(--um-navy)',
                                }}
                              />
                              <span className={styles.countLabel}>{fmt(s.citation_count)}</span>
                            </div>
                          </td>
                          <td className={styles.tdOA}>
                            <span className={oaClass(s.oa_type || (s.is_oa ? 'green' : 'closed'))}>
                              {s.oa_type || (s.is_oa ? 'open' : 'closed')}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}