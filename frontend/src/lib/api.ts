/** Собирает URL запроса: same-origin /api/… или http://localhost:8000 в dev. */
export function resolveApiUrl(path: string): string {
  const raw = import.meta.env.VITE_API_BASE_URL;
  const hasBase = raw !== undefined && raw !== null && String(raw).trim() !== "";
  if (!hasBase) {
    return path;
  }
  const base = String(raw).replace(/\/$/, "");
  // docker-compose раньше задавал VITE_API_BASE_URL=/api при путях /api/… → /api/api/…
  if ((base === "/api" || base.endsWith("/api")) && path.startsWith("/api/")) {
    return path;
  }
  return `${base}${path}`;
}

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

export type DeveloperOut = {
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
  developer_id?: string | null;
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

export type SourceCrawlScheduleOut = {
  id: string;
  source_type: string;
  name: string | null;
  display_label: string;
  enabled: boolean;
  fetch_frequency_min: number;
  last_fetch_at: string | null;
  last_success_at: string | null;
  backoff_until: string | null;
  is_due: boolean;
  next_expected_enqueue_at: string | null;
};

export type SourceCrawlScheduleListOut = {
  server_now: string;
  items: SourceCrawlScheduleOut[];
  due_count: number;
};

export type DiagnosticsOverviewOut = {
  now: string;
  db_ok: boolean;
  redis_ok: boolean;
  rq_default_queue_count: number;
  alembic_version?: string | null;
  alert_critical_count: number;
  alert_warning_count: number;
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

export type ParsedIndicatorOut = {
  id: string;
  indicator_name: string;
  period: string;
  value: number;
  change_pct: number | null;
  unit: string | null;
  source_name: string | null;
  created_at: string;
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
  competitor_mentions_names: string[];
  developer_mentions: string[];
  developer_mentions_names: string[];
  created_at: string;
  updated_at: string;
};

export type IndicatorTelegramReportGroup = {
  title: string;
  keywords: string[];
};

export type IndicatorTelegramConfigOut = {
  enabled: boolean;
  channel_username: string;
  include_keywords: string[];
  exclude_keywords: string[];
  match_whole_words: boolean;
  backfill_limit: number;
  backfill_until_date: string | null;
  include_in_report: boolean;
  ai_in_report: boolean;
  report_groups: IndicatorTelegramReportGroup[];
  last_message_id: number | null;
  last_fetch_at: string | null;
  last_error: string | null;
};

export type IndicatorTelegramSection = {
  title: string;
  keywords: string[];
  posts: Array<{
    id: string;
    text: string | null;
    image_path: string | null;
    post_url: string;
    published_at: string | null;
    matched_keywords: string[];
  }>;
  ai_text: string | null;
  ai_json: Record<string, unknown> | null;
};

export type IndicatorTelegramPostOut = {
  id: string;
  channel_username: string;
  message_id: number;
  post_url: string;
  text: string | null;
  image_path: string | null;
  published_at: string | null;
  matched_keywords: string[];
  created_at: string;
};

export type NewsEntitySyncOut = {
  checked: number;
  updated_developer: number;
  updated_competitor: number;
  sources_touched: number;
  overwrite: boolean;
  source_id: string | null;
};

export type MaxParserStatusOut = {
  token_configured: boolean;
  token_source: string;
  api_base: string;
  token_valid: boolean | null;
  bot_info?: any;
  verify_error?: string | null;
};

export type VkParserStatusOut = {
  token_configured: boolean;
  token_source: string;
  api_base: string;
  api_version: string;
  token_valid: boolean | null;
  verify_error?: string | null;
};

export type MonitoringAlertOut = {
  id: string;
  severity: "info" | "warning" | "critical";
  code: string;
  message: string;
  source_id?: string | null;
  source_label?: string | null;
  meta: Record<string, unknown>;
};

export type MonitoringAlertsOut = {
  generated_at: string;
  critical_count: number;
  warning_count: number;
  info_count: number;
  items: MonitoringAlertOut[];
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

  let res: Response;
  try {
    res = await fetch(resolveApiUrl(path), { ...init, headers });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Network error";
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        "Нет связи с API. Проверьте backend, nginx (/api) и миграцию: docker compose exec backend alembic upgrade head",
      );
    }
    throw e instanceof Error ? e : new Error(msg);
  }
  if (!res.ok) {
    // On 401 with expired token: try refresh and retry once
    if (res.status === 401 && accessToken && authRefreshHandler && !isRetry) {
      const newToken = await authRefreshHandler();
      if (newToken) return request<T>(path, init, newToken, true);
    }
    // Extract error message
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    let errMsg: string | null = null;
    if (ct.includes("application/json")) {
      try {
        const j: any = await res.json();
        const detail = j?.detail;
        if (typeof detail === "string") {
          errMsg = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          // FastAPI 422: detail is array of { loc, msg, type }
          const parts = detail.map((e: { loc?: string[]; msg?: string }) => {
            const field = Array.isArray(e.loc) ? e.loc.filter((x) => x !== "body").pop() : null;
            const msg = e?.msg || "Validation error";
            return field ? `${field}: ${msg}` : msg;
          });
          errMsg = parts.join("; ");
        } else {
          errMsg = JSON.stringify(j);
        }
      } catch {
        // JSON parse failed, fall through to text
      }
    }
    if (errMsg) throw new Error(errMsg);
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
    list: (accessToken: string, params?: { q?: string; source_id?: string; competitor_id?: string; offset?: number; limit?: number }) => {
      const sp = new URLSearchParams();
      if (params?.q) sp.set("q", params.q);
      if (params?.source_id) sp.set("source_id", params.source_id);
      if (params?.competitor_id) sp.set("competitor_id", params.competitor_id);
      if (params?.offset != null) sp.set("offset", String(params.offset));
      if (params?.limit != null) sp.set("limit", String(params.limit));
      const qs = sp.toString() ? `?${sp.toString()}` : "";
      return request<{ items: NewsItemOut[]; total: number }>(`/api/news${qs}`, { method: "GET" }, accessToken);
    },
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/news/${id}`, { method: "DELETE" }, accessToken),
    syncEntityLinks: (accessToken: string, params?: { source_id?: string; overwrite?: boolean }) => {
      const sp = new URLSearchParams();
      if (params?.source_id) sp.set("source_id", params.source_id);
      if (params?.overwrite) sp.set("overwrite", "true");
      const qs = sp.toString() ? `?${sp.toString()}` : "";
      return request<NewsEntitySyncOut>(`/api/news/sync-entity-links${qs}`, { method: "POST" }, accessToken);
    },
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
  developers: {
    list: (accessToken: string, q?: string) => {
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      return request<{ items: DeveloperOut[]; total: number }>(`/api/developers${qs}`, { method: "GET" }, accessToken);
    },
    create: (accessToken: string, payload: Partial<DeveloperOut>) =>
      request<DeveloperOut>("/api/developers", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    update: (accessToken: string, id: string, payload: Partial<DeveloperOut>) =>
      request<DeveloperOut>(`/api/developers/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, accessToken),
    delete: (accessToken: string, id: string) =>
      request<void>(`/api/developers/${id}`, { method: "DELETE" }, accessToken),
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
    syncEntityLinks: (accessToken: string, sourceId: string, overwrite = false) => {
      const qs = overwrite ? "?overwrite=true" : "";
      return request<NewsEntitySyncOut>(`/api/sources/${sourceId}/sync-entity-links${qs}`, { method: "POST" }, accessToken);
    },
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
    crawlSchedule: (accessToken: string, includeDisabled?: boolean) => {
      const qs = includeDisabled ? "?include_disabled=true" : "";
      return request<SourceCrawlScheduleListOut>(`/api/monitoring/crawl-schedule${qs}`, { method: "GET" }, accessToken);
    },
    enqueueDue: (accessToken: string, batchLimit?: number) => {
      const sp = new URLSearchParams();
      if (batchLimit != null) sp.set("batch_limit", String(batchLimit));
      const qs = sp.toString() ? `?${sp.toString()}` : "";
      return request<{ enqueued: number }>(`/api/monitoring/enqueue-due${qs}`, { method: "POST" }, accessToken);
    },
    alerts: (accessToken: string, params?: { include_disabled?: boolean; limit?: number }) => {
      const sp = new URLSearchParams();
      if (params?.include_disabled) sp.set("include_disabled", "true");
      if (params?.limit != null) sp.set("limit", String(params.limit));
      const qs = sp.toString() ? `?${sp.toString()}` : "";
      return request<MonitoringAlertsOut>(`/api/monitoring/alerts${qs}`, { method: "GET" }, accessToken);
    },
  },
  telegramParser: {
    status: (accessToken: string) =>
      request<{
        credentials_configured: boolean;
        session_string_used: boolean;
        session_dir: string;
        session_file_exists: boolean;
        session_authorized: boolean | null;
        verify_error?: string | null;
        config_source?: string;
      }>("/api/telegram-parser/status", { method: "GET" }, accessToken),
    config: (accessToken: string) =>
      request<{ api_id_set: boolean; api_hash_set: boolean; session_string_set: boolean; config_source: string }>(
        "/api/telegram-parser/config",
        { method: "GET" },
        accessToken,
      ),
    updateConfig: (
      accessToken: string,
      payload: { api_id?: number | null; api_hash?: string | null; session_string?: string | null },
    ) =>
      request<{ api_id_set: boolean; api_hash_set: boolean; session_string_set: boolean; config_source: string }>(
        "/api/telegram-parser/config",
        { method: "PUT", body: JSON.stringify(payload) },
        accessToken,
      ),
    qrStart: (accessToken: string, api_id: number, api_hash: string) =>
      request<{ poll_id: string; qr_url: string; session_string?: string | null }>("/api/telegram-parser/qr-start", {
        method: "POST",
        body: JSON.stringify({ api_id, api_hash }),
      }, accessToken),
    qrPoll: (accessToken: string, pollId: string) =>
      request<{ status: string; session_string?: string | null; error?: string | null }>(
        `/api/telegram-parser/qr-poll/${pollId}`,
        { method: "GET" },
        accessToken,
      ),
    qr2fa: (accessToken: string, pollId: string, password: string) =>
      request<{ status: string; session_string?: string | null; error?: string | null }>(
        "/api/telegram-parser/qr-2fa",
        { method: "POST", body: JSON.stringify({ poll_id: pollId, password }) },
        accessToken,
      ),
  },
  maxParser: {
    status: (accessToken: string) => request<MaxParserStatusOut>("/api/max-parser/status", { method: "GET" }, accessToken),
    config: (accessToken: string) =>
      request<{ bot_token_set: boolean; token_source: string }>("/api/max-parser/config", { method: "GET" }, accessToken),
    updateConfig: (accessToken: string, payload: { bot_token?: string | null }) =>
      request<{ bot_token_set: boolean; token_source: string }>(
        "/api/max-parser/config",
        { method: "PUT", body: JSON.stringify(payload) },
        accessToken,
      ),
    testBot: (accessToken: string, token: string) =>
      request<{ ok: boolean; bot_info?: any; error?: string | null }>(
        "/api/max-parser/test-bot",
        { method: "POST", body: JSON.stringify({ token }) },
        accessToken,
      ),
    testFetch: (accessToken: string, payload: { channel_id: string; limit?: number }) =>
      request<{ fetched: number; sample: Array<{ id?: string; text?: string; date?: string }> }>(
        "/api/max-parser/test-fetch",
        { method: "POST", body: JSON.stringify(payload) },
        accessToken,
      ),
  },
  vkParser: {
    status: (accessToken: string) => request<VkParserStatusOut>("/api/vk-parser/status", { method: "GET" }, accessToken),
    config: (accessToken: string) =>
      request<{ access_token_set: boolean; token_source: string }>("/api/vk-parser/config", { method: "GET" }, accessToken),
    updateConfig: (accessToken: string, payload: { access_token?: string | null }) =>
      request<{ access_token_set: boolean; token_source: string }>(
        "/api/vk-parser/config",
        { method: "PUT", body: JSON.stringify(payload) },
        accessToken,
      ),
    testToken: (accessToken: string, token: string) =>
      request<{ ok: boolean; error?: string | null }>(
        "/api/vk-parser/test-token",
        { method: "POST", body: JSON.stringify({ token }) },
        accessToken,
      ),
    testFetch: (accessToken: string, payload: { group_id: string; limit?: number }) =>
      request<{ fetched: number; sample: Array<{ id?: string; text?: string; date?: string; url?: string | null }> }>(
        "/api/vk-parser/test-fetch",
        { method: "POST", body: JSON.stringify(payload) },
        accessToken,
      ),
  },
  diagnostics: {
    overview: (accessToken: string) => request<DiagnosticsOverviewOut>("/api/diagnostics/overview", { method: "GET" }, accessToken),
    runSourceNow: (accessToken: string, sourceId: string) =>
      request<{ job_id: string }>(`/api/diagnostics/sources/${sourceId}/run-now`, { method: "POST" }, accessToken),
    rebuildNewsClusters: (accessToken: string) =>
      request<{ job_id: string }>("/api/diagnostics/rebuild-news-clusters", { method: "POST" }, accessToken),
    jobStatus: (accessToken: string, jobId: string) =>
      request<{ job_id: string; status: string; result?: any; exc_info?: string | null }>(`/api/diagnostics/jobs/${jobId}`, { method: "GET" }, accessToken),
  },
  indicators: {
    cnyRubLatest: (accessToken: string) =>
      request<IndicatorLatestOut>("/api/indicators/cny-rub/latest", { method: "GET" }, accessToken),
    parseDocument: (async function parseDoc(accessToken: string, file: File, isRetry = false) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(resolveApiUrl("/api/indicators/parse-document"), {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      if (!res.ok) {
        if (res.status === 401 && accessToken && authRefreshHandler && !isRetry) {
          const newToken = await authRefreshHandler();
          if (newToken) return parseDoc(newToken, file, true);
        }
        const j = await res.json().catch(() => ({}));
        const detail = j?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail) && detail.length > 0
              ? (detail[0] as { msg?: string })?.msg || JSON.stringify(detail)
              : res.statusText;
        throw new Error(msg);
      }
      return res.json() as Promise<Array<{ indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null }>>;
    }) as (accessToken: string, file: File) => Promise<Array<{ indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null }>>,
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
    parsedNames: (accessToken: string) =>
      request<string[]>("/api/indicators/parsed/names", { method: "GET" }, accessToken),
    parsedList: (accessToken: string, indicatorName?: string) =>
      request<{ items: ParsedIndicatorOut[]; total: number }>(
        `/api/indicators/parsed${indicatorName ? `?indicator_name=${encodeURIComponent(indicatorName)}` : ""}`,
        { method: "GET" },
        accessToken,
      ),
    parsedHistory: (accessToken: string, indicatorName: string) =>
      request<{ indicator_name: string; items: Array<{ period: string; value: number; unit?: string | null }> }>(
        `/api/indicators/parsed/history?indicator_name=${encodeURIComponent(indicatorName)}`,
        { method: "GET" },
        accessToken,
      ),
    parsedCreate: (accessToken: string, payload: { indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null; source_name?: string | null }) =>
      request<ParsedIndicatorOut>("/api/indicators/parsed/single", { method: "POST", body: JSON.stringify(payload) }, accessToken),
    parsedUpdate: (accessToken: string, id: string, payload: Partial<{ indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null; source_name?: string | null }>) =>
      request<ParsedIndicatorOut>(`/api/indicators/parsed/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, accessToken),
    parsedDelete: (accessToken: string, id: string) =>
      request<void>(`/api/indicators/parsed/${id}`, { method: "DELETE" }, accessToken),
    telegramConfig: {
      get: (accessToken: string) =>
        request<IndicatorTelegramConfigOut>("/api/indicators/telegram/config", { method: "GET" }, accessToken),
      update: (
        accessToken: string,
        payload: Partial<{
          enabled: boolean;
          channel_username: string;
          include_keywords: string[];
          exclude_keywords: string[];
          match_whole_words: boolean;
          backfill_limit: number;
          backfill_until_date: string | null;
          include_in_report: boolean;
          ai_in_report: boolean;
          report_groups: IndicatorTelegramReportGroup[];
        }>,
      ) =>
        request<IndicatorTelegramConfigOut>("/api/indicators/telegram/config", { method: "PUT", body: JSON.stringify(payload) }, accessToken),
      posts: (accessToken: string, params?: { limit?: number; offset?: number }) => {
        const sp = new URLSearchParams();
        if (params?.limit != null) sp.set("limit", String(params.limit));
        if (params?.offset != null) sp.set("offset", String(params.offset));
        const qs = sp.toString() ? `?${sp.toString()}` : "";
        return request<{ items: IndicatorTelegramPostOut[]; total: number }>(`/api/indicators/telegram/posts${qs}`, { method: "GET" }, accessToken);
      },
      collectNow: (accessToken: string, params?: { reset_history?: boolean }) => {
        const qs = params?.reset_history ? "?reset_history=true" : "";
        return request<{ status: string; channel?: string; fetched?: number; matched?: number; inserted?: number; updated?: number }>(
          `/api/indicators/telegram/collect-now${qs}`,
          { method: "POST" },
          accessToken,
        );
      },
      deletePost: (accessToken: string, id: string) =>
        request<void>(`/api/indicators/telegram/posts/${id}`, { method: "DELETE" }, accessToken),
      previewFilter: (
        accessToken: string,
        payload: {
          text: string;
          include_keywords: string[];
          exclude_keywords: string[];
          match_whole_words: boolean;
        },
      ) =>
        request<{ keep: boolean; reason: string; matched_keywords: string[] }>(
          "/api/indicators/telegram/preview-filter",
          { method: "POST", body: JSON.stringify(payload) },
          accessToken,
        ),
    },
  },
  reportConfig: {
    get: (accessToken: string) =>
      request<{
        title: string;
        subtitle: string;
        company_name: string;
        company_address: string;
        footer_text: string;
        include_news: boolean;
        include_indicators: boolean;
        include_regions: boolean;
        include_competitors: boolean;
        include_developers: boolean;
        include_general_news: boolean;
        include_clusters: boolean;
        include_region_unassigned: boolean;
        disabled_competitor_ids: string[];
        disabled_developer_ids: string[];
        disabled_region_ids: string[];
        date_range_days: number;
        report_month: string | null;
      }>("/api/report-config", { method: "GET" }, accessToken),
    update: (
      accessToken: string,
      payload: Partial<{
        title: string;
        subtitle: string;
        company_name: string;
        company_address: string;
        footer_text: string;
        include_news: boolean;
        include_indicators: boolean;
        include_regions: boolean;
        include_competitors: boolean;
        include_developers: boolean;
        include_general_news: boolean;
        include_clusters: boolean;
        include_region_unassigned: boolean;
        disabled_competitor_ids: string[];
        disabled_developer_ids: string[];
        disabled_region_ids: string[];
        date_range_days: number;
        report_month: string | null;
      }>,
    ) =>
      request<{
        title: string;
        subtitle: string;
        company_name: string;
        company_address: string;
        footer_text: string;
        include_news: boolean;
        include_indicators: boolean;
        include_regions: boolean;
        include_competitors: boolean;
        include_developers: boolean;
        include_general_news: boolean;
        include_clusters: boolean;
        include_region_unassigned: boolean;
        disabled_competitor_ids: string[];
        disabled_developer_ids: string[];
        disabled_region_ids: string[];
        date_range_days: number;
        report_month: string | null;
      }>("/api/report-config", { method: "PUT", body: JSON.stringify(payload) }, accessToken),
  },
  newsFilter: {
    get: (accessToken: string) =>
      request<{
        global_exclude_keywords: string[];
        global_include_keywords: string[];
        match_whole_words: boolean;
      }>("/api/news-filter", { method: "GET" }, accessToken),
    update: (
      accessToken: string,
      payload: {
        global_exclude_keywords?: string[];
        global_include_keywords?: string[];
        match_whole_words?: boolean;
      },
    ) =>
      request<{
        global_exclude_keywords: string[];
        global_include_keywords: string[];
        match_whole_words: boolean;
      }>("/api/news-filter", { method: "PUT", body: JSON.stringify(payload) }, accessToken),
    preview: (accessToken: string, payload: { text: string; source_id?: string }) =>
      request<{ keep: boolean; reason: string; matched_keywords: string[] }>(
        "/api/news-filter/preview",
        { method: "POST", body: JSON.stringify(payload) },
        accessToken,
      ),
    cleanup: (accessToken: string, payload?: { source_id?: string; dry_run?: boolean }) =>
      request<{ deleted: number; total_checked: number; dry_run: boolean }>(
        "/api/news-filter/cleanup",
        { method: "POST", body: JSON.stringify(payload || {}) },
        accessToken,
      ),
  },
  aiConfig: {
    get: (accessToken: string) =>
      request<{
        provider: string;
        api_key_set: boolean;
        model: string;
        ai_request_delay_seconds: number;
        ai_max_retries: number;
        ai_retry_base_seconds: number;
        prompt_news: string;
        prompt_competitors: string;
        prompt_developers: string;
        prompt_indicators: string;
        prompt_regions: string;
        prompt_clusters: string;
      }>("/api/ai-config", { method: "GET" }, accessToken),
    update: (
      accessToken: string,
      payload: Partial<{
        provider: string;
        api_key: string;
        model: string;
        ai_request_delay_seconds: number;
        ai_max_retries: number;
        ai_retry_base_seconds: number;
        prompt_news: string;
        prompt_competitors: string;
        prompt_developers: string;
        prompt_indicators: string;
        prompt_regions: string;
        prompt_clusters: string;
      }>,
    ) =>
      request<{
        provider: string;
        api_key_set: boolean;
        model: string;
        ai_request_delay_seconds: number;
        ai_max_retries: number;
        ai_retry_base_seconds: number;
        prompt_news: string;
        prompt_competitors: string;
        prompt_developers: string;
        prompt_indicators: string;
        prompt_regions: string;
        prompt_clusters: string;
      }>("/api/ai-config", { method: "PUT", body: JSON.stringify(payload) }, accessToken),
    test: (accessToken: string) =>
      request<{
        ok: boolean;
        provider: string;
        model: string;
        latency_ms: number;
        message: string;
        response_preview: string | null;
      }>("/api/ai-config/test", { method: "POST" }, accessToken),
  },
  reports: {
    generate: (
      accessToken: string,
      params?: { date_from?: string; date_to?: string; date_range_days?: number; report_month?: string },
    ) =>
      request<{
        report_config: { title: string; subtitle: string; company_name: string; company_address: string; footer_text: string };
        period: { date_from: string; date_to: string };
        ai_stats: {
          calls: number;
          succeeded: number;
          failed: number;
          labels_failed: string[];
          request_delay_seconds: number;
          max_retries: number;
        };
        processed_news: string | null;
        processed_competitors: string | null;
        processed_indicators: string | null;
        processed_regions: string | null;
        processed_clusters: string | null;
        processed_news_json: Record<string, unknown> | null;
        processed_indicators_json: Record<string, unknown> | null;
        processed_clusters_json: Record<string, unknown> | null;
        processed_competitors_by_name: Record<string, string>;
        processed_developers_by_name: Record<string, string>;
        processed_regions_by_name: Record<string, string>;
        processed_competitors_by_name_json: Record<string, Record<string, unknown>>;
        processed_developers_by_name_json: Record<string, Record<string, unknown>>;
        processed_regions_by_name_json: Record<string, Record<string, unknown>>;
      }>("/api/reports/generate", {
        method: "POST",
        body: JSON.stringify(params || {}),
      }, accessToken),
    generatePdf: async (
      accessToken: string,
      params?: {
        date_from?: string;
        date_to?: string;
        date_range_days?: number;
        report_month?: string;
        processed_indicators?: string | null;
        processed_news?: string | null;
        processed_competitors?: string | null;
        processed_regions?: string | null;
        processed_clusters?: string | null;
        processed_news_json?: Record<string, unknown> | null;
        processed_indicators_json?: Record<string, unknown> | null;
        processed_clusters_json?: Record<string, unknown> | null;
        processed_competitors_by_name?: Record<string, string>;
        processed_developers_by_name?: Record<string, string>;
        processed_regions_by_name?: Record<string, string>;
        processed_competitors_by_name_json?: Record<string, Record<string, unknown>>;
        processed_developers_by_name_json?: Record<string, Record<string, unknown>>;
        processed_regions_by_name_json?: Record<string, Record<string, unknown>>;
        indicator_telegram_sections?: IndicatorTelegramSection[];
      },
    ): Promise<Blob> => {
      const res = await fetch(resolveApiUrl("/api/reports/generate-pdf"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(params || {}),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      return res.blob();
    },
    generateHtml: async (
      accessToken: string,
      params?: { date_from?: string; date_to?: string; date_range_days?: number; report_month?: string },
    ): Promise<Blob> => {
      const res = await fetch(resolveApiUrl("/api/reports/generate-html"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(params || {}),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      return res.blob();
    },
    publishHtml: (
      accessToken: string,
      params?: {
        date_from?: string;
        date_to?: string;
        date_range_days?: number;
        report_month?: string;
        skip_ai?: boolean;
        processed_indicators?: string | null;
        processed_news?: string | null;
        processed_clusters?: string | null;
        processed_news_json?: Record<string, unknown> | null;
        processed_indicators_json?: Record<string, unknown> | null;
        processed_clusters_json?: Record<string, unknown> | null;
        processed_competitors_by_name?: Record<string, string>;
        processed_developers_by_name?: Record<string, string>;
        processed_regions_by_name?: Record<string, string>;
        processed_competitors_by_name_json?: Record<string, Record<string, unknown>>;
        processed_developers_by_name_json?: Record<string, Record<string, unknown>>;
        processed_regions_by_name_json?: Record<string, Record<string, unknown>>;
        indicator_telegram_sections?: IndicatorTelegramSection[];
      },
    ) =>
      request<{
        id: string;
        filename: string;
        public_path: string;
        title: string;
        date_from: string;
        date_to: string;
        report_month: string | null;
        created_at: string;
      }>("/api/reports/publish-html", { method: "POST", body: JSON.stringify(params || {}) }, accessToken),
    listPublished: (accessToken: string, limit = 20) =>
      request<{
        items: Array<{
          id: string;
          filename: string;
          public_path: string;
          title: string;
          date_from: string;
          date_to: string;
          report_month: string | null;
          created_at: string;
        }>;
      }>(`/api/reports/published?limit=${limit}`, { method: "GET" }, accessToken),
    deletePublished: (accessToken: string, reportId: string) =>
      request<{ ok: boolean }>(`/api/reports/published/${encodeURIComponent(reportId)}`, { method: "DELETE" }, accessToken),
    generateStream: async (
      accessToken: string,
      params: { date_from?: string; date_to?: string; date_range_days?: number; report_month?: string } | undefined,
      onEvent: (event: Record<string, unknown>) => void,
      signal?: AbortSignal,
    ) => {
      const res = await fetch(resolveApiUrl("/api/reports/generate-stream"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(params || {}),
        signal,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const reader = res.body?.getReader();
      if (!reader) throw new Error("Нет тела ответа");
      const decoder = new TextDecoder();
      let buffer = "";
      let result: Record<string, unknown> | null = null;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const ev = JSON.parse(line.slice(6)) as Record<string, unknown>;
            onEvent(ev);
            if (ev.type === "complete" && ev.result) result = ev.result as Record<string, unknown>;
            if (ev.type === "error") throw new Error(String(ev.message || "Ошибка генерации"));
          }
        }
      }
      if (!result) throw new Error("Поток завершился без результата");
      return result;
    },
  },
};

