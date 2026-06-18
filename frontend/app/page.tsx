'use client';
import { useState, useEffect, useCallback } from 'react';
import Header, { TabId } from './components/Header';
import ErrorBanner from './components/ErrorBanner';
import styles from './page.module.css';

// Lazy-loaded tab components
import dynamic from 'next/dynamic';
const Overview        = dynamic(() => import('./components/tabs/Overview'));
const Publications    = dynamic(() => import('./components/tabs/Publications'));
const Fields          = dynamic(() => import('./components/tabs/Fields'));
const OpenAccess      = dynamic(() => import('./components/tabs/OpenAccess'));
const Authors         = dynamic(() => import('./components/tabs/Authors'));
const Departments     = dynamic(() => import('./components/tabs/Departments'));
const Patents         = dynamic(() => import('./components/tabs/Patents'));
const Collaborations  = dynamic(() => import('./components/tabs/Collaborations'));
const Journals        = dynamic(() => import('./components/tabs/Journals'));
const CitationSources = dynamic(() => import('./components/tabs/CitationSources'));

type TabProps = { yearFrom: number; yearTo: number; onDimError: () => void; onOaError: () => void };
const PANELS: { id: TabId; C: React.ComponentType<TabProps> }[] = [
  { id: 'overview', C: Overview },
  { id: 'publications', C: Publications },
  { id: 'fields', C: Fields },
  { id: 'openaccess', C: OpenAccess },
  { id: 'authors', C: Authors },
  { id: 'departments', C: Departments },
  { id: 'patents', C: Patents },
  { id: 'collaborations', C: Collaborations },
  { id: 'journals', C: Journals },
  { id: 'citationsources', C: CitationSources },
];

export default function Page() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [yearFrom, setYearFrom] = useState(2018);
  const [yearTo, setYearTo] = useState(new Date().getFullYear());
  const [mountedTabs, setMountedTabs] = useState<Set<TabId>>(new Set(['overview']));
  const [dimError, setDimError] = useState(false);
  const [oaError, setOaError] = useState(false);
  // Gate the URL writer until after we've read the initial ?tab= on mount, so we
  // don't clobber it. (Reading in a useState initializer fails: it runs during
  // SSR where window is undefined, and hydration keeps that server value.)
  const [hydrated, setHydrated] = useState(false);

  // Read the active tab from the URL (?tab=) once on mount, so returning from a
  // sub-page (e.g. /authors/[id] → /?tab=authors) restores the right tab.
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get('tab') as TabId | null;
    if (t) {
      setActiveTab(t);
      setMountedTabs(prev => new Set([...prev, t]));
    }
    setHydrated(true);
  }, []);

  // Keep the URL in sync with the active tab (replaceState — no history spam).
  useEffect(() => {
    if (!hydrated) return;
    const url = new URL(window.location.href);
    if (url.searchParams.get('tab') !== activeTab) {
      url.searchParams.set('tab', activeTab);
      window.history.replaceState(null, '', url.toString());
    }
  }, [activeTab, hydrated]);

  const handleTabChange = useCallback((tab: TabId) => {
    setActiveTab(tab);
    setMountedTabs(prev => new Set([...prev, tab]));
  }, []);

  const handleYearChange = useCallback((from: number, to: number) => {
    if (from <= to) { setYearFrom(from); setYearTo(to); }
  }, []);

  const tabProps = { yearFrom, yearTo, onDimError: () => setDimError(true), onOaError: () => setOaError(true) };

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Header
          activeTab={activeTab}
          onTabChange={handleTabChange}
          yearFrom={yearFrom}
          yearTo={yearTo}
          onYearChange={handleYearChange}
        />

        <div className={styles.banners}>
          {dimError && <ErrorBanner message="Dimensions AI data temporarily unavailable. OpenAlex sections still active." />}
          {oaError  && <ErrorBanner message="OpenAlex data temporarily unavailable." critical />}
        </div>

        <main id="main-content" className={styles.main}>
          {PANELS.map(({ id, C }) => mountedTabs.has(id) && (
            <div
              key={id}
              role="tabpanel"
              id={`panel-${id}`}
              aria-labelledby={`tab-${id}`}
              tabIndex={0}
              hidden={activeTab !== id}
            >
              <C {...tabProps} />
            </div>
          ))}
        </main>

        <footer className={styles.footer}>
          <span>© {new Date().getFullYear()} University of Mississippi · Research Analytics</span>
          <span>
            Data: <a href="https://openalex.org" target="_blank" rel="noreferrer">OpenAlex</a>
            {' '}&amp;{' '}
            <a href="https://www.dimensions.ai" target="_blank" rel="noreferrer">Dimensions AI</a>
          </span>
          <a href="/api/cache-status" target="_blank" rel="noreferrer">Cache Status</a>
        </footer>
      </div>
    </>
  );
}