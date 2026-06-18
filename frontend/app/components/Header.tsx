'use client';
import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import styles from './Header.module.css';
import { api } from '../../lib/api';

// Ordered by the research lifecycle: who & where → what → outputs → dissemination
// → impact → partnerships → commercialization.
const TABS = [
  { id: 'overview',         label: 'Overview',          icon: '⬡' },
  { id: 'authors',          label: 'Authors',            icon: '👥' },
  { id: 'departments',      label: 'Departments',        icon: '🏛' },
  { id: 'fields',           label: 'Research Fields',    icon: '🏷' },
  { id: 'publications',     label: 'Publications',       icon: '📄' },
  { id: 'journals',         label: 'Publication Venues', icon: '📚' },
  { id: 'openaccess',       label: 'Open Access',        icon: '🔓' },
  { id: 'citationsources',  label: 'Citation Sources',   icon: '🔗' },
  { id: 'collaborations',   label: 'Collaborations',     icon: '🌐' },
  { id: 'patents',          label: 'Patents',            icon: '💡' },
] as const;

export type TabId = typeof TABS[number]['id'];

// Tabs whose data has a year dimension and therefore honor the year range.
// The rest are served from year-agnostic aggregates, so the filter is inert
// there and we disable it rather than let the control silently do nothing.
const YEAR_AWARE_TABS = new Set<TabId>([
  'overview', 'publications', 'openaccess', 'journals', 'patents',
]);

const currentYear = new Date().getFullYear();
const MIN_YEAR = 2018;
const YEARS = Array.from({ length: currentYear - MIN_YEAR + 1 }, (_, i) => currentYear - i);

interface Props {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  yearFrom: number;
  yearTo: number;
  onYearChange: (from: number, to: number) => void;
}

// `id` is the author id for author results — used to deep-link to the faculty
// profile. Publication results just switch to the Publications tab.
interface SearchResult { type: 'author' | 'pub'; label: string; sub: string; tab: TabId; id?: string; }

export default function Header({ activeTab, onTabChange, yearFrom, yearTo, onYearChange }: Props) {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Draft year range — the selects only edit this. Nothing downstream (tabs,
  // data fetches) changes until the user clicks Apply. Re-sync if the applied
  // range changes from outside.
  const [draftFrom, setDraftFrom] = useState(yearFrom);
  const [draftTo, setDraftTo] = useState(yearTo);
  useEffect(() => { setDraftFrom(yearFrom); setDraftTo(yearTo); }, [yearFrom, yearTo]);
  const yearDirty = draftFrom !== yearFrom || draftTo !== yearTo;
  const yearAware = YEAR_AWARE_TABS.has(activeTab);

  // Arrow-key navigation within the tablist (WAI-ARIA tabs pattern).
  const handleTabKey = (e: React.KeyboardEvent, idx: number) => {
    let next = idx;
    if (e.key === 'ArrowRight') next = (idx + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = TABS.length - 1;
    else return;
    e.preventDefault();
    onTabChange(TABS[next].id);
    tabRefs.current[next]?.focus();
  };

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
            out.push({ type: 'author', label: a.name, sub: a.primary_field ?? 'Author', tab: 'authors', id: a.id });
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

  const handleResultClick = (r: SearchResult) => {
    setSearch('');
    setShowDropdown(false);
    // Author results deep-link straight to the faculty profile; everything else
    // just switches to the relevant tab.
    if (r.type === 'author' && r.id) {
      router.push(`/authors/${r.id}`);
    } else {
      onTabChange(r.tab);
    }
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
            <label htmlFor="dashboard-search" className="sr-only">Search publications and authors</label>
            <input
              id="dashboard-search"
              className={styles.search}
              type="search"
              placeholder="Search publications & authors…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
              onFocus={() => results.length > 0 && setShowDropdown(true)}
              role="combobox"
              aria-expanded={showDropdown}
              aria-controls="search-results"
              aria-autocomplete="list"
            />
            {showDropdown && (
              <ul className={styles.dropdown} id="search-results" role="listbox" aria-label="Search results">
                {results.length === 0 ? (
                  <li className={styles.noResults} role="option" aria-disabled="true">No results found.</li>
                ) : results.map((r, i) => (
                  <li
                    key={i}
                    className={styles.result}
                    role="option"
                    tabIndex={0}
                    onClick={() => handleResultClick(r)}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleResultClick(r); } }}
                  >
                    <span className={styles.resultType}>{r.type}</span>
                    <span className={styles.resultLabel}>{r.label}</span>
                    <span className={styles.resultSub}>{r.sub}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Year filter — two dropdowns + Apply. Selecting a year only edits the
              draft; the applied range (and the tabs) update on Apply. Disabled on
              tabs whose data has no year dimension, so the control never lies. */}
          <form
            className={`${styles.yearFilter} ${yearAware ? '' : styles.yearFilterMuted}`}
            role="group"
            aria-label="Filter by year range"
            title={yearAware ? undefined : "This view isn’t filtered by year"}
            onSubmit={e => { e.preventDefault(); if (yearAware && yearDirty) onYearChange(draftFrom, draftTo); }}
          >
            <span className={styles.yearLabel} aria-hidden="true">Years</span>
            <select
              className={styles.yearSelect}
              aria-label="From year"
              value={draftFrom}
              disabled={!yearAware}
              onChange={e => {
                const v = Number(e.target.value);
                setDraftFrom(v);
                setDraftTo(Math.max(v, draftTo));
              }}
            >
              {YEARS.slice().reverse().map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <span className={styles.yearSep} aria-hidden="true">–</span>
            <select
              className={styles.yearSelect}
              aria-label="To year"
              value={draftTo}
              disabled={!yearAware}
              onChange={e => {
                const v = Number(e.target.value);
                setDraftTo(v);
                setDraftFrom(Math.min(draftFrom, v));
              }}
            >
              {YEARS.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <button
              type="submit"
              className={styles.yearApply}
              disabled={!yearAware || !yearDirty}
              aria-label="Apply year range"
            >
              Apply
            </button>
          </form>
        </div>
      </div>

      {/* Tab bar */}
      <nav className={styles.tabBar} role="tablist" aria-label="Dashboard sections">
        {TABS.map((tab, i) => (
          <button
            key={tab.id}
            ref={el => { tabRefs.current[i] = el; }}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
            onClick={() => onTabChange(tab.id)}
            onKeyDown={e => handleTabKey(e, i)}
          >
            <span className={styles.tabIcon} aria-hidden="true">{tab.icon}</span>
            <span className={styles.tabLabel}>{tab.label}</span>
          </button>
        ))}
      </nav>
    </header>
  );
}