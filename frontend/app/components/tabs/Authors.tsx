'use client';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api, Author } from '../../../lib/api';
import { fmt } from '../../../lib/utils';
import DataTable, { Column } from '../DataTable';
import Skeleton from '../Skeleton';
import Badge from '../Badge';
import styles from './Authors.module.css';

interface Props {
  yearFrom: number;
  yearTo: number;
  onDimError: () => void;
  onOaError: () => void;
}

const PAGE_SIZE = 25;

export default function Authors({ onOaError }: Props) {
  const router = useRouter();
  const [authors, setAuthors] = useState<Author[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [search, setSearch] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const requestIdRef = useRef(0);

  const loadPage = useCallback(async (pageNum: number, q: string, replace = false) => {
    if (pageNum === 1) replace = true;

    const requestId = ++requestIdRef.current;

    try {
      const res = await api.authorsTop(q, pageNum, PAGE_SIZE);

      if (requestId !== requestIdRef.current) return;

      const items: Author[] = res.data?.items ?? res.data ?? [];
      const count: number = res.data?.total ?? items.length;

      setAuthors(prev => (replace ? items : [...prev, ...items]));
      setTotal(count);
      setPage(pageNum);
    } catch {
      if (requestId !== requestIdRef.current) return;
      onOaError();
    }
  }, [onOaError]);

  useEffect(() => {
    loadPage(1, '').finally(() => setInitialLoading(false));
  }, [loadPage]);

  const handleSearch = (q: string) => {
    setSearch(q);
    clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      setSearchLoading(true);
      loadPage(1, q)
        .finally(() => setSearchLoading(false));
    }, 400);
  };

  const handleLoadMore = async () => {
    setLoadingMore(true);
    await loadPage(page + 1, search);
    setLoadingMore(false);
  };

  // List view is intentionally non-competitive: neutral, informative fields
  // only. Click a row to open the author's full profile page (metrics live there).
  const columns: Column<Author>[] = [
    {
      key: 'name',
      label: 'Name',
    },
    {
      key: 'primary_field',
      label: 'Primary Field',
      render: v => (v ? String(v) : '—'),
    },
    {
      key: 'department',
      label: 'Department',
      render: v => (v ? String(v) : '—'),
    },
    {
      key: 'orcid',
      label: 'ORCID',
      render: v =>
        v ? (
          <a
            href={String(v)}
            target="_blank"
            rel="noreferrer"
            className={styles.orcidLink}
            onClick={e => e.stopPropagation()}
            aria-label="ORCID profile (opens in a new tab)"
          >
            <span aria-hidden="true">🆔</span>
          </a>
        ) : (
          '—'
        ),
    },
    {
      key: 'scholar_url',
      label: 'Google Scholar',
      render: v =>
        v ? (
          <a
            href={String(v)}
            target="_blank"
            rel="noreferrer"
            className={styles.orcidLink}
            onClick={e => e.stopPropagation()}
            aria-label="Google Scholar profile (opens in a new tab)"
          >
            <span aria-hidden="true">🎓</span> Profile
          </a>
        ) : (
          '—'
        ),
    },
  ];

  const rows = authors;
  const hasMore = total !== null && authors.length < total;

  return (
    <div className={`${styles.root} fadeInUp`}>
      <div className={styles.toolbar}>
        <h3 className={styles.heading}>
          Authors
          {total !== null && (
            <span className={styles.headingCount}> ({fmt(total)} total)</span>
          )}
        </h3>

        <div className={styles.toolbarRight}>
          <input
            className={styles.searchInput}
            type="search"
            placeholder="Search authors…"
            aria-label="Search authors"
            value={search}
            onChange={e => handleSearch(e.target.value)}
          />
          {searchLoading && (
            <span className={styles.searchLoading}>Searching…</span>
          )}
          <Badge source="openalex" />
        </div>
    </div>

      {initialLoading ? (
        <Skeleton height={400} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={rows}
            onRowClick={row => router.push(`/authors/${(row as Author).id}`)}
          />

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
        </>
      )}
    </div>
  );
}