'use client';
import { useState, useRef, useEffect } from 'react';
import styles from './Header.module.css';
import { api } from '../../lib/api';

const TABS = [
  { id: 'overview',       label: 'Overview',        icon: '⬡' },
  { id: 'publications',   label: 'Publications',     icon: '📄' },
  { id: 'fields',         label: 'Research Fields',  icon: '🏷' },
  { id: 'openaccess',     label: 'Open Access',      icon: '🔓' },
  { id: 'authors',        label: 'Authors',          icon: '👥' },
  { id: 'collaborations', label: 'Collaborations',   icon: '🌐' },
  { id: 'journals',       label: 'Journals',         icon: '📚' },
] as const;

export type TabId = typeof TABS[number]['id'];

const currentYear = new Date().getFullYear();
const YEARS = Array.from({ length: currentYear - 1999 }, (_, i) => currentYear - i);

interface Props {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  yearFrom: number;
  yearTo: number;
  onYearChange: (from: number, to: number) => void;
}

interface SearchResult { type: 'author' | 'pub'; label: string; sub: string; tab: TabId; }

export default function Header({ activeTab, onTabChange, yearFrom, yearTo, onYearChange }: Props) {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSearch = (q: string) => {
    setSearch(q);
    clearTimeout(searchTimer.current);
    if (q.length < 2) { setShowDropdown(false); return; }
    searchTimer.current = setTimeout(async () => {
      const out: SearchResult[] = [];
      try {
        const authResp = await api.authorsTop(q, 1, 10);
        const authors = authResp.data?.items ?? [];
        for (const a of authors.slice(0, 4)) {
          if (a.name.toLowerCase().includes(q.toLowerCase())) {
            out.push({ type: 'author', label: a.name, sub: `${a.works_count} publications`, tab: 'authors' });
          }
        }
      } catch {}
      try {
        const pubsResp = await api.pubsList(1, 5);
        for (const p of (pubsResp.data?.items ?? [])) {
          if ((p.title ?? '').toLowerCase().includes(q.toLowerCase())) {
            out.push({ type: 'pub', label: p.title ?? '', sub: `${p.year ?? ''} · ${p.type ?? ''}`, tab: 'publications' });
          }
        }
      } catch {}
      setResults(out.slice(0, 6));
      setShowDropdown(true);
    }, 350);
  };

  const handleResultClick = (tab: TabId) => {
    onTabChange(tab);
    setSearch('');
    setShowDropdown(false);
  };

  return (
    <header className={styles.header}>
      <div className={styles.top}>
        <div className={styles.brand}>
          <div className={styles.logo}>UM</div>
          <div>
            <div className={styles.title}>University of Mississippi Research Dashboard</div>
            <div className={styles.subtitle}>Oxford, MS · OpenAlex &amp; Dimensions AI</div>
          </div>
        </div>

        <div className={styles.controls}>
          {/* Search */}
          <div className={styles.searchWrap} ref={searchRef}>
            <input
              className={styles.search}
              type="search"
              placeholder="Search publications & authors…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
              onFocus={() => results.length > 0 && setShowDropdown(true)}
            />
            {showDropdown && (
              <div className={styles.dropdown}>
                {results.length === 0 ? (
                  <div className={styles.noResults}>No results found.</div>
                ) : results.map((r, i) => (
                  <div key={i} className={styles.result} onClick={() => handleResultClick(r.tab)}>
                    <span className={styles.resultType}>{r.type}</span>
                    <span className={styles.resultLabel}>{r.label}</span>
                    <span className={styles.resultSub}>{r.sub}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Year filter — two dropdowns */}
          <div className={styles.yearFilter}>
            <span className={styles.yearLabel}>Years</span>
            <select
              className={styles.yearSelect}
              value={yearFrom}
              onChange={e => {
                const v = Number(e.target.value);
                onYearChange(v, Math.max(v, yearTo));
              }}
            >
              {YEARS.slice().reverse().map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <span className={styles.yearSep}>–</span>
            <select
              className={styles.yearSelect}
              value={yearTo}
              onChange={e => {
                const v = Number(e.target.value);
                onYearChange(Math.min(yearFrom, v), v);
              }}
            >
              {YEARS.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <nav className={styles.tabBar}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
            onClick={() => onTabChange(tab.id)}
          >
            <span className={styles.tabIcon}>{tab.icon}</span>
            <span className={styles.tabLabel}>{tab.label}</span>
          </button>
        ))}
      </nav>
    </header>
  );
}