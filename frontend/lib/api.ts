// ── Types ─────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T;
  source: string;
  cached: boolean;
  fetched_at: string;
  institution_id: string;
  source_error?: string;
}

export interface YearCount { year: number; count: number; }
export interface FieldCount { field_name: string; count: number; }
export interface OAStatus  { oa_status: string; count: number; }
export interface TypeCount  { type: string; count: number; }

export interface InstitutionOverview {
  works_count: number;
  cited_by_count: number;
  h_index: number;
  i10_index: number;
  counts_by_year: Array<{ year: number; works_count: number; cited_by_count: number }>;
  display_name: string;
}

export interface Publication {
  id: string;
  title: string;
  doi?: string;
  year?: number;
  type?: string;
  oa_status?: string;
  is_oa?: boolean;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Author {
  id: string;
  name: string;
  total_publications: number;
  um_publications: number;
  cited_by_count: number;
  h_index: number;
  orcid?: string | null;
}

export interface AuthorWork {
  title: string;
  doi?: string;
  year?: number;
  citations: number;
}

export interface Journal { name: string; count: number; }

export interface CollabInstitution { name: string; count: number; country: string; }
export interface CollabCountry { country: string; country_code: string; count: number; }

export interface GrantsSummary {
  total_grants: number;
  total_funding_usd: number;
  by_funder: Array<{ name: string; count: number; total_usd: number }>;
}

export interface Grant {
  id?: string;
  title?: string;
  funder_org_name?: string;
  funding_usd?: number;
  start_date?: string;
  end_date?: string;
}

export interface GrantYearData { year: string; count: number; total_usd: number; }

export interface TrialsSummary {
  total: number;
  active_count: number;
  completed_count: number;
  recruiting_count: number;
  by_phase: Array<{ phase: string; count: number }>;
}

export interface Trial {
  id?: string;
  title?: string;
  status?: string;
  phase?: string;
  date?: string;
  conditions?: string[];
}

export interface Patent {
  id?: string;
  title?: string;
  filing_date?: string;
  grant_date?: string;
}

export interface OATrendItem {
  year: number;
  oa_count: number;
  total: number;
  oa_percentage: number;
}

export interface PubsByYearData {
  openalex: YearCount[];
  dimensions: YearCount[];
  source_error?: string;
}

export interface CitationSourceRow {
  source_name:    string;
  publisher:      string;
  citation_count: number;
  is_oa:          boolean;
  oa_type:        string;
}

// ── Fetch helper ───────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:5000';

async function apiFetch<T>(path: string, params?: Record<string, string | number>): Promise<ApiResponse<T>> {
  const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])) : '';
  const res = await fetch(`${API_BASE}${path}${qs}`, { cache: 'no-store' });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw Object.assign(new Error(body.error || res.statusText), { sourceError: body.source_error });
  }
  return res.json();
}

// ── API methods ────────────────────────────────────────────────────

export const api = {
  institutionOverview: () =>
    apiFetch<InstitutionOverview>('/api/institution/overview'),

  pubsByYear: (yearFrom?: number, yearTo?: number) =>
    apiFetch<PubsByYearData>('/api/publications/by-year',
      yearFrom && yearTo ? { year_from: yearFrom, year_to: yearTo } : undefined),

  pubsByField: () =>
    apiFetch<FieldCount[]>('/api/publications/by-field'),

  pubsOpenAccess: () =>
    apiFetch<OAStatus[]>('/api/publications/open-access'),

  pubsByType: () =>
    apiFetch<TypeCount[]>('/api/publications/by-type'),

  pubsList: (page = 1, perPage = 25, type = '', yearFrom?: number, yearTo?: number) =>
    apiFetch<PaginatedResult<Publication>>('/api/publications/list', {
      page, per_page: perPage,
      ...(type ? { type } : {}),
      ...(yearFrom ? { year_from: yearFrom } : {}),
      ...(yearTo ? { year_to: yearTo } : {}),
    }),

  authorsTop: (search = '', page = 1, perPage = 25) =>
    apiFetch<{ items: Author[]; total: number; page: number; per_page: number }>('/api/authors/top', {
      page, per_page: perPage, ...(search ? { search } : {}),
    }),

  authorWorks: (id: string) =>
    apiFetch<AuthorWork[]>(`/api/authors/${id}/works`),

  authorExpertise: (id: string, orcid?: string) =>
    apiFetch<Array<{
      keyword: string;
      total_score: number;
      sources: string[];
      type: string;
    }>>(`/api/authors/${id}/expertise`, orcid ? { orcid } : undefined),

  authorCitationSources: (id: string) =>
    apiFetch<CitationSourceRow[]>(`/api/authors/${id}/citation-sources`),

  journalsTop: () =>
    apiFetch<Journal[]>('/api/journals/top'),

  collabInstitutions: () =>
    apiFetch<CollabInstitution[]>('/api/collaborations/institutions'),

  collabCountries: () =>
    apiFetch<CollabCountry[]>('/api/collaborations/countries'),

  grantsSummary: () =>
    apiFetch<GrantsSummary>('/api/grants/summary'),

  grantsList: (page = 1, perPage = 25) =>
    apiFetch<PaginatedResult<Grant>>('/api/grants/list', { page, per_page: perPage }),

  grantsByYear: () =>
    apiFetch<GrantYearData[]>('/api/grants/by-year'),

  trialsSummary: () =>
    apiFetch<TrialsSummary>('/api/trials/summary'),

  trialsList: (page = 1, perPage = 25, search = '') =>
    apiFetch<PaginatedResult<Trial>>('/api/trials/list', {
      page, per_page: perPage, ...(search ? { search } : {}),
    }),

  patentsByYear: () =>
    apiFetch<Array<{ year: string; count: number }>>('/api/patents/by-year'),

  patentsList: (page = 1, perPage = 25) =>
    apiFetch<PaginatedResult<Patent>>('/api/patents/list', { page, per_page: perPage }),

  oaTrend: () =>
    apiFetch<OATrendItem[]>('/api/open-access/trend'),
};