const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type UserOut = {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type RegionOut = {
  id: string;
  name: string;
  federal_subjects: string[];
  keywords: string[];
  geographic_aliases: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CompetitorOut = {
  id: string;
  name: string;
  aliases: string[];
  tags: string[];
  region_ids: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ParsingTemplateOut = {
  id: string;
  name: string;
  version: number;
  template_json: any;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type SourceOut = {
  id: string;
  source_type: string;
  name?: string | null;
  base_url?: string | null;
  feed_url?: string | null;
  tg_channel_username?: string | null;
  region_tags: string[];
  competitor_id?: string | null;
  enabled: boolean;
  fetch_frequency_min: number;
  priority: number;
  delay_ms: number;
  max_requests_per_minute: number;
  retries: number;
  respect_robots_txt: boolean;
  parsing_template_id?: string | null;
  settings_json: any;
  last_fetch_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
  backoff_until?: string | null;
  created_at: string;
  updated_at: string;
};

export type SourceHealthOut = {
  id: string;
  source_type: string;
  name?: string | null;
  base_url?: string | null;
  feed_url?: string | null;
  tg_channel_username?: string | null;
  enabled: boolean;
  fetch_frequency_min: number;
  priority: number;
  last_fetch_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
  backoff_until?: string | null;
};

export type DiagnosticsOverviewOut = {
  now: string;
  db_ok: boolean;
  redis_ok: boolean;
  rq_default_queue_count: number;
  alembic_version?: string | null;
};

export type IndicatorLatestOut = {
  series: string;
  value: number;
  unit?: string | null;
  source_name?: string | null;
  period_date: string;
  fetched_at: string;
  updated_at_msk?: string | null;
};

export type IndicatorPointOut = {
  period_date: string;
  value: number;
};

export type IndicatorHistoryOut = {
  series: string;
  unit?: string | null;
  items: IndicatorPointOut[];
};

export type NewsItemOut = {
  id: string;
  source_id: string | null;
  source_name: string | null;
  competitor_id: string | null;
  url: string;
  canonical_url: string;
  title: string | null;
  author: string | null;
  published_at: string | null;
  snippet: string | null;
  content_text: string | null;
  region_ids: string[];
  topic_tags: string[];
  competitor_mentions: string[];
  created_at: string;
  updated_at: string;
};

/** Handler for 401: tries refresh, returns new access token or null. Set by AuthProvider. */
let authRefreshHandler: (() => Promise<string | null>) | null = null;

export function setAuthRefreshHandler(handler: (() => Promise<string | null>) | null) {
  authRefreshHandler = handler;
}

async function request<T>(path: string, init: RequestInit = {}, accessToken?: string, isRetry = false): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    // On 401 with expired token: try refresh and retry once
    if (res.status === 401 && accessToken && authRefreshHandler && !isRetry) {
      const newToken = await authRefreshHandler();
      if (newToken) return request<T>(path, init, newToken, true);
    }
    // Extract error message
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (ct.includes("application/json")) {
      try {
        const j: any = await res.json();
        const detail = j?.detail;
        if (typeof detail === "string") throw new Error(detail);
        throw new Error(JSON.stringify(j));
      } catch {
        // JSON parse failed, fall through to text
      }
    }
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<TokenPair>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
    refresh: (refresh_token: string) =>
      request<TokenPair>("/api/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token }) }),
    me: (accessToken: string) => request<UserOut>("/api/auth/me", { method: "GET" }, accessToken),
    bootstrapAdmin: (email: string, password: string, full_name?: string) =>
      request<UserOut>("/api/admin/bootstrap", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name }),
      }),
  },
  news: {
    list: (accessToken: string, params?: { q?: string; source_id?: string; offset?: number; limit?: number }) => {
      const sp = new URLSearchParams();
      if (params?.q) sp.set("q", params.q);
      if (params?.source_id) sp.set("source_id", params.source_id);
      if (params?.offset != null) sp.set("offset", String(params.offset));
      if (params?.limit != null) sp.set("limit", String(params.limit));
      const qs = sp.toString() ? `?${sp.toString()}` : "";
      return request<{ items: NewsItemOut[]; total: number }>(`/api/news${qs}`, { method: "GET" }, accessToken);
    },
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/news/${id}`, { method: "DELETE" }, accessToken),
  },
  regions: {
    list: (accessToken: string, q?: string) => {
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      return request<{ items: RegionOut[]; total: number }>(`/api/regions${qs}`, { method: "GET" }, accessToken);
    },
    create: (accessToken: string, payload: Partial<RegionOut>) =>
      request<RegionOut>("/api/regions", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    update: (accessToken: string, id: string, payload: Partial<RegionOut>) =>
      request<RegionOut>(`/api/regions/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, accessToken),
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/regions/${id}`, { method: "DELETE" }, accessToken),
  },
  competitors: {
    list: (accessToken: string, q?: string) => {
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      return request<{ items: CompetitorOut[]; total: number }>(`/api/competitors${qs}`, { method: "GET" }, accessToken);
    },
    create: (accessToken: string, payload: Partial<CompetitorOut>) =>
      request<CompetitorOut>("/api/competitors", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    update: (accessToken: string, id: string, payload: Partial<CompetitorOut>) =>
      request<CompetitorOut>(`/api/competitors/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, accessToken),
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/competitors/${id}`, { method: "DELETE" }, accessToken),
  },
  parsingTemplates: {
    list: (accessToken: string, q?: string) => {
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      return request<{ items: ParsingTemplateOut[]; total: number }>(`/api/parsing-templates${qs}`, { method: "GET" }, accessToken);
    },
    create: (accessToken: string, payload: Partial<ParsingTemplateOut>) =>
      request<ParsingTemplateOut>("/api/parsing-templates", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    update: (accessToken: string, id: string, payload: Partial<ParsingTemplateOut>) =>
      request<ParsingTemplateOut>(`/api/parsing-templates/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, accessToken),
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/parsing-templates/${id}`, { method: "DELETE" }, accessToken),
  },
  sources: {
    list: (accessToken: string) =>
      request<{ items: SourceOut[]; total: number }>(`/api/sources`, { method: "GET" }, accessToken),
    create: (accessToken: string, payload: Partial<SourceOut>) =>
      request<SourceOut>("/api/sources", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    update: (accessToken: string, id: string, payload: Partial<SourceOut>) =>
      request<SourceOut>(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, accessToken),
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/sources/${id}`, { method: "DELETE" }, accessToken),
    cleanupNews: (accessToken: string, sourceId: string) =>
      request<{ deleted: number; total_checked: number }>(`/api/sources/${sourceId}/cleanup-news`, { method: "POST" }, accessToken),
  },
  templates: {
    test: (accessToken: string, url: string, template_json: any) =>
      request<{
        url: string;
        title?: string | null;
        author?: string | null;
        published_at_raw?: string | null;
        published_at?: string | null;
        body_text_preview?: string | null;
        body_text_length: number;
      }>(
        "/api/templates/test",
        { method: "POST", body: JSON.stringify({ url, template_json }) },
        accessToken,
      ),
  },
  monitoring: {
    sources: (accessToken: string, only_failed?: boolean) => {
      const qs = only_failed ? "?only_failed=true" : "";
      return request<{ items: SourceHealthOut[]; total: number }>(`/api/monitoring/sources${qs}`, { method: "GET" }, accessToken);
    },
  },
  diagnostics: {
    overview: (accessToken: string) => request<DiagnosticsOverviewOut>("/api/diagnostics/overview", { method: "GET" }, accessToken),
    runSourceNow: (accessToken: string, sourceId: string) =>
      request<{ job_id: string }>(`/api/diagnostics/sources/${sourceId}/run-now`, { method: "POST" }, accessToken),
    jobStatus: (accessToken: string, jobId: string) =>
      request<{ job_id: string; status: string; result?: any; exc_info?: string | null }>(`/api/diagnostics/jobs/${jobId}`, { method: "GET" }, accessToken),
  },
  indicators: {
    cnyRubLatest: (accessToken: string) =>
      request<IndicatorLatestOut>("/api/indicators/cny-rub/latest", { method: "GET" }, accessToken),
    parseDocument: async (accessToken: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/indicators/parse-document`, {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail || res.statusText);
      }
      return res.json() as Promise<Array<{ indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null }>>;
    },
    importParsed: (accessToken: string, payload: { rows: Array<{ indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null }>; source_name?: string | null }) =>
      request<{ inserted: number; batch_id: string }>("/api/indicators/import-parsed", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    cnyRubHistory: (accessToken: string, days: number = 30) =>
      request<IndicatorHistoryOut>(`/api/indicators/cny-rub/history?days=${encodeURIComponent(String(days))}`, { method: "GET" }, accessToken),
    cnyRubCollectNow: (accessToken: string) =>
      request<{ status: string; series: string; period_date: string; value: number; unit?: string; source_name?: string }>(
        "/api/indicators/cny-rub/collect-now",
        { method: "POST" },
        accessToken,
      ),
  },
};

