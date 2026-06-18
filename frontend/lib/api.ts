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

// List-view author: NEUTRAL fields only (no competitive metrics, random order).
export interface Author {
  id: string;
  name: string;
  orcid?: string | null;
  scholar_url?: string | null;
  primary_field?: string | null;
  department?: string | null;
}

// Modal-only detail: the full metrics live here, never in the list view.
export interface AuthorDetail extends Author {
  total_publications: number;
  um_publications: number;
  cited_by_count: number;
  h_index: number;
  i10_index: number;
}

export interface Department {
  name: string;
  publication_count: number;
  citation_count: number;
}

export interface AuthorWork {
  title: string;
  doi?: string;
  year?: number;
  citations: number;
}

export interface AuthorGrant {
  grant_id?: string | null;
  title?: string | null;
  funder?: string | null;
  funding_usd: number;
  start_year?: number | null;
  role?: string | null;
}

export interface AuthorPatent {
  id: string;
  title?: string | null;
  year?: number | null;
  times_cited: number;
  inventors: string[];
  filing_status?: string | null;
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
  id: string;
  title?: string;
  year?: number | null;
  times_cited: number;
  inventors: string[];
  assignees: string[];
  filing_status?: string | null;
}

export interface PatentsSummary {
  total_patents: number;
  total_cited: number;
  unique_inventors: number;
  by_year: YearCount[];
  top_inventors: Array<{ name: string; count: number }>;
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

// Default to relative URLs so requests go through the Next.js dev proxy
// (next.config.mjs → 127.0.0.1:5000). Hitting "localhost:5000" directly from
// the browser resolves to IPv6 ::1, where macOS AirPlay/Control Center squats
// and returns 403. Override with NEXT_PUBLIC_API_BASE for a remote backend.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '';

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

  pubsOpenAccess: (yearFrom?: number, yearTo?: number) =>
    apiFetch<OAStatus[]>('/api/publications/open-access', {
      ...(yearFrom ? { year_from: yearFrom } : {}),
      ...(yearTo ? { year_to: yearTo } : {}),
    }),

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

  authorDetail: (id: string) =>
    apiFetch<AuthorDetail>(`/api/authors/${id}`),

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

  authorGrants: (id: string) =>
    apiFetch<AuthorGrant[]>(`/api/authors/${id}/grants`),

  authorPatents: (id: string) =>
    apiFetch<AuthorPatent[]>(`/api/authors/${id}/patents`),

  journalsTop: (search = '', yearFrom?: number, yearTo?: number) =>
    apiFetch<Journal[]>('/api/journals/top', {
      ...(search ? { search } : {}),
      ...(yearFrom ? { year_from: yearFrom } : {}),
      ...(yearTo ? { year_to: yearTo } : {}),
    }),

  collabInstitutions: () =>
    apiFetch<CollabInstitution[]>('/api/collaborations/institutions'),

  collabCountries: () =>
    apiFetch<CollabCountry[]>('/api/collaborations/countries'),

  grantsSummary: () =>
    apiFetch<GrantsSummary>('/api/grants/summary'),

  departments: () =>
    apiFetch<Department[]>('/api/departments'),

  oaTrend: (yearFrom?: number, yearTo?: number) =>
    apiFetch<OATrendItem[]>('/api/open-access/trend', {
      ...(yearFrom ? { year_from: yearFrom } : {}),
      ...(yearTo ? { year_to: yearTo } : {}),
    }),

  patentsSummary: (yearFrom?: number, yearTo?: number) =>
    apiFetch<PatentsSummary>('/api/patents/summary', {
      ...(yearFrom ? { year_from: yearFrom } : {}),
      ...(yearTo ? { year_to: yearTo } : {}),
    }),

  patentsList: (yearFrom?: number, yearTo?: number) =>
    apiFetch<Patent[]>('/api/patents/list', {
      ...(yearFrom ? { year_from: yearFrom } : {}),
      ...(yearTo ? { year_to: yearTo } : {}),
    }),
};