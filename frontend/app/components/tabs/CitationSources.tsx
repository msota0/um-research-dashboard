'use client';
/**
 * CitationSources.tsx
 *
 * Tab: "Citation Sources"
 *
 * Flow:
 *   1. Load all UM Oxford authors (paginated, same as Authors tab)
 *   2. User clicks an author row → expand inline to show their citation sources
 *   3. Citation sources panel: list of journals/publishers that cite that
 *      author's work, sorted by count, with OA badge on each source
 *
 * Data sources:
 *   Authors list   → OpenAlex  /api/authors/top
 *   Citation sources → Dimensions  /api/authors/{id}/citation-sources
 *
 * No publications or raw citations are ever displayed.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, Author } from '../../../lib/api';
import { fmt, oaClass } from '../../../lib/utils';
import Skeleton from '../Skeleton';
import Badge from '../Badge';
import styles from './CitationSources.module.css';

// ── Types ──────────────────────────────────────────────────────────────────

interface CitationSourceRow {
  source_name:    string;
  publisher:      string;
  citation_count: number;
  is_oa:          boolean;
  oa_type:        string;   // gold | green | hybrid | bronze | closed | unknown
}

interface Props {
  yearFrom:   number;
  yearTo:     number;
  onDimError: () => void;
  onOaError:  () => void;
}

const PAGE_SIZE = 25;

// ── Component ──────────────────────────────────────────────────────────────

export default function CitationSources({ onOaError, onDimError }: Props) {
  // ── author list state
  const [authors,        setAuthors]        = useState<Author[]>([]);
  const [total,          setTotal]          = useState<number | null>(null);
  const [page,           setPage]           = useState(1);
  const [loadingAuthors, setLoadingAuthors] = useState(true);
  const [loadingMore,    setLoadingMore]    = useState(false);
  const [search,         setSearch]         = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // ── expanded author + their sources
  const [expandedId,      setExpandedId]      = useState<string | null>(null);
  const [sourcesMap,      setSourcesMap]      = useState<Record<string, CitationSourceRow[]>>({});
  const [loadingSourceId, setLoadingSourceId] = useState<string | null>(null);
  const [sourceSearch,    setSourceSearch]    = useState('');
  const [sourceFilter,    setSourceFilter]    = useState<'all' | 'oa' | 'closed'>('all');

  // ── load author list ────────────────────────────────────────────────────────

  const loadPage = useCallback(async (pageNum: number, q: string, replace = false) => {
    try {
      const res = await api.authorsTop(q, pageNum, PAGE_SIZE);
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
    setExpandedId(null);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setLoadingAuthors(true);
      loadPage(1, q).finally(() => setLoadingAuthors(false));
    }, 400);
  };

  const handleLoadMore = async () => {
    setLoadingMore(true);
    await loadPage(page + 1, search);
    setLoadingMore(false);
  };

  // ── expand / collapse author row ───────────────────────────────────────────

  const handleAuthorClick = async (author: Author) => {
    // Collapse if already open
    if (expandedId === author.id) {
      setExpandedId(null);
      setSourceSearch('');
      setSourceFilter('all');
      return;
    }

    setExpandedId(author.id);
    setSourceSearch('');
    setSourceFilter('all');

    // Already fetched?
    if (sourcesMap[author.id] !== undefined) return;

    setLoadingSourceId(author.id);
    try {
      const res = await apiFetchCitationSources(author.id);
      setSourcesMap(prev => ({ ...prev, [author.id]: res }));
    } catch {
      onDimError();
      setSourcesMap(prev => ({ ...prev, [author.id]: [] }));
    } finally {
      setLoadingSourceId(null);
    }
  };

  // ── derived: filtered sources for expanded author ──────────────────────────

  const rawSources: CitationSourceRow[] = expandedId ? (sourcesMap[expandedId] ?? []) : [];

  const visibleSources = rawSources.filter(s => {
    const matchText = !sourceSearch ||
      s.source_name.toLowerCase().includes(sourceSearch.toLowerCase()) ||
      s.publisher.toLowerCase().includes(sourceSearch.toLowerCase());
    const matchOA =
      sourceFilter === 'all'    ? true :
      sourceFilter === 'oa'     ? s.is_oa :
      /* closed */                !s.is_oa;
    return matchText && matchOA;
  });

  const totalCitations = rawSources.reduce((n, s) => n + s.citation_count, 0);
  const oaSources      = rawSources.filter(s => s.is_oa).length;
  const hasMore = total !== null && authors.length < total;

  return (
    <div className={`${styles.root} fadeInUp`}>

      {/* ── Header toolbar ── */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <h3 className={styles.heading}>
            Citation Sources
            {total !== null && (
              <span className={styles.headingCount}> — {fmt(total)} authors</span>
            )}
          </h3>
          <p className={styles.subheading}>
            Select an author to see which journals and publishers cite their work,
            and whether those sources are open access.
          </p>
        </div>
        <div className={styles.toolbarRight}>
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

      {/* ── Author list ── */}
      {loadingAuthors ? (
        <Skeleton height={420} />
      ) : (
        <div className={styles.authorList}>
          {authors.map(author => {
            const isExpanded = expandedId === author.id;
            const isLoading  = loadingSourceId === author.id;
            const sources    = sourcesMap[author.id];

            return (
              <div
                key={author.id}
                className={`${styles.authorBlock} ${isExpanded ? styles.authorBlockOpen : ''}`}
              >
                {/* ── Author row (always visible) ── */}
                <button
                  className={styles.authorRow}
                  onClick={() => handleAuthorClick(author)}
                  aria-expanded={isExpanded}
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

                  {/* Summary pill — shown after sources are loaded */}
                  {sources && sources.length > 0 && (
                    <span className={styles.summaryPill}>
                      {sources.length} sources
                    </span>
                  )}

                  <span className={`${styles.chevron} ${isExpanded ? styles.chevronOpen : ''}`}>
                    ▾
                  </span>
                </button>

                {/* ── Expanded sources panel ── */}
                {isExpanded && (
                  <div className={styles.sourcesPanel}>

                    {isLoading ? (
                      <Skeleton height={200} />
                    ) : !sources || sources.length === 0 ? (
                      <p className={styles.emptyMsg}>
                        No citation source data found for this author in Dimensions AI.
                      </p>
                    ) : (
                      <>
                        {/* ── Summary bar ── */}
                        <div className={styles.summaryBar}>
                          <div className={styles.summaryCard}>
                            <span className={styles.summaryVal}>{fmt(totalCitations)}</span>
                            <span className={styles.summaryLabel}>Total incoming citations</span>
                          </div>
                          <div className={styles.summaryCard}>
                            <span className={styles.summaryVal}>{rawSources.length}</span>
                            <span className={styles.summaryLabel}>Unique sources</span>
                          </div>
                          <div className={styles.summaryCard}>
                            <span className={styles.summaryVal}>{oaSources}</span>
                            <span className={styles.summaryLabel}>Open-access sources</span>
                          </div>
                          <div className={styles.summaryCard}>
                            <span className={`${styles.summaryVal} ${styles.summaryPct}`}>
                              {rawSources.length > 0
                                ? Math.round((oaSources / rawSources.length) * 100)
                                : 0}%
                            </span>
                            <span className={styles.summaryLabel}>OA source rate</span>
                          </div>
                        </div>

                        {/* ── Source controls ── */}
                        <div className={styles.sourceControls}>
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
                          <span className={styles.sourceCount}>
                            {visibleSources.length} of {rawSources.length} sources
                          </span>
                        </div>

                        {/* ── Sources table ── */}
                        {visibleSources.length === 0 ? (
                          <p className={styles.emptyMsg}>No sources match your filter.</p>
                        ) : (
                          <div className={styles.tableWrap}>
                            <table className={styles.table}>
                              <thead>
                                <tr>
                                  <th className={styles.thRank}>#</th>
                                  <th className={styles.thSource}>Source</th>
                                  <th className={styles.thPublisher}>Publisher</th>
                                  <th className={styles.thCount}>Citations received</th>
                                  <th className={styles.thOA}>OA Status</th>
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
                                    </td>
                                    <td className={styles.tdPublisher}>
                                      {s.publisher || '—'}
                                    </td>
                                    <td className={styles.tdCount}>
                                      <div className={styles.countBar}>
                                        <div
                                          className={styles.countBarFill}
                                          style={{
                                            width: `${Math.min(100, (s.citation_count / (visibleSources[0]?.citation_count || 1)) * 100)}%`,
                                            background: s.is_oa ? 'var(--oa-green)' : 'var(--um-navy)',
                                          }}
                                        />
                                        <span className={styles.countLabel}>{fmt(s.citation_count)}</span>
                                      </div>
                                    </td>
                                    <td className={styles.tdOA}>
                                      <span className={oaClass(s.oa_type || (s.is_oa ? 'gold' : 'closed'))}>
                                        {s.oa_type || (s.is_oa ? 'open' : 'closed')}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* ── Load more authors ── */}
          {hasMore && (
            <div className={styles.loadMoreRow}>
              {loadingMore ? (
                <Skeleton height={36} />
              ) : (
                <button className={styles.loadMoreBtn} onClick={handleLoadMore}>
                  Show more authors
                  <span className={styles.loadMoreMeta}>
                    &nbsp;({authors.length} of {fmt(total!)} shown)
                  </span>
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Fetch helper (not in shared api.ts yet) ────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:5000';

async function apiFetchCitationSources(authorId: string): Promise<CitationSourceRow[]> {
  const res = await fetch(
    `${API_BASE}/api/authors/${authorId}/citation-sources`,
    { cache: 'no-store' }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || res.statusText);
  }
  const json = await res.json();
  return json.data ?? [];
}
