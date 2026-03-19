'use client';
import { useState, useEffect, useCallback } from 'react';
import Header, { TabId } from './components/Header';
import ErrorBanner from './components/ErrorBanner';
import styles from './page.module.css';

// Lazy-loaded tab components
import dynamic from 'next/dynamic';
const Overview       = dynamic(() => import('./components/tabs/Overview'));
const Publications   = dynamic(() => import('./components/tabs/Publications'));
const Fields         = dynamic(() => import('./components/tabs/Fields'));
const OpenAccess     = dynamic(() => import('./components/tabs/OpenAccess'));
const Authors        = dynamic(() => import('./components/tabs/Authors'));
const Grants         = dynamic(() => import('./components/tabs/Grants'));
const Trials         = dynamic(() => import('./components/tabs/Trials'));
const Patents        = dynamic(() => import('./components/tabs/Patents'));
const Collaborations = dynamic(() => import('./components/tabs/Collaborations'));
const Journals       = dynamic(() => import('./components/tabs/Journals'));

export default function Page() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [yearFrom, setYearFrom] = useState(2000);
  const [yearTo, setYearTo] = useState(new Date().getFullYear());
  const [mountedTabs, setMountedTabs] = useState<Set<TabId>>(new Set(['overview']));
  const [dimError, setDimError] = useState(false);
  const [oaError, setOaError] = useState(false);

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

      <main className={styles.main}>
        {mountedTabs.has('overview')       && <div className={activeTab !== 'overview'       ? styles.hidden : ''}><Overview       {...tabProps} /></div>}
        {mountedTabs.has('publications')   && <div className={activeTab !== 'publications'   ? styles.hidden : ''}><Publications   {...tabProps} /></div>}
        {mountedTabs.has('fields')         && <div className={activeTab !== 'fields'         ? styles.hidden : ''}><Fields         {...tabProps} /></div>}
        {mountedTabs.has('openaccess')     && <div className={activeTab !== 'openaccess'     ? styles.hidden : ''}><OpenAccess     {...tabProps} /></div>}
        {mountedTabs.has('authors')        && <div className={activeTab !== 'authors'        ? styles.hidden : ''}><Authors        {...tabProps} /></div>}
        {mountedTabs.has('grants')         && <div className={activeTab !== 'grants'         ? styles.hidden : ''}><Grants         {...tabProps} /></div>}
        {mountedTabs.has('trials')         && <div className={activeTab !== 'trials'         ? styles.hidden : ''}><Trials         {...tabProps} /></div>}
        {mountedTabs.has('patents')        && <div className={activeTab !== 'patents'        ? styles.hidden : ''}><Patents        {...tabProps} /></div>}
        {mountedTabs.has('collaborations') && <div className={activeTab !== 'collaborations' ? styles.hidden : ''}><Collaborations {...tabProps} /></div>}
        {mountedTabs.has('journals')       && <div className={activeTab !== 'journals'       ? styles.hidden : ''}><Journals       {...tabProps} /></div>}
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
    </>
  );
}
