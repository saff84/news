import { useEffect, useRef, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, CheckCircle2, FileText, Loader2, Save, Trash2, XCircle } from "lucide-react";
import { api, type CompetitorOut, type DeveloperOut, type RegionOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

type GeneralNewsThemeForm = {
  title: string;
  keywords: string;
};

type ReportConfig = {
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
  general_news_themes: GeneralNewsThemeForm[];
};

const DEFAULT_GENERAL_NEWS_THEMES: GeneralNewsThemeForm[] = [
  { title: "Ипотека и ставка", keywords: "ипотек, ипотеч, ключев, ставк, цб, центробанк, рефинанс" },
  { title: "Ввод жилья и строительство", keywords: "ввод, введен, росстат, жиль, строитель, млн м, млн кв" },
  { title: "Законодательство и регулирование", keywords: "закон, госдум, минстрой, регулир, норматив, постановлен" },
  { title: "Рынок и цены", keywords: "цен, стоимост, продаж, спрос, предложен, рынок, новостро, девелоп" },
  { title: "Госпрограммы и субсидии", keywords: "семейн, льгот, субсид, господдерж, dom.rf, дом.рф, госпрограмм" },
  { title: "Прочее", keywords: "" },
];

function parseThemeKeywords(raw: string): string[] {
  return raw
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function themesFromApi(items: Array<{ title: string; keywords: string[] }> | undefined): GeneralNewsThemeForm[] {
  if (!items?.length) return DEFAULT_GENERAL_NEWS_THEMES;
  return items.map((g) => ({
    title: g.title,
    keywords: (g.keywords || []).join(", "),
  }));
}

function toggleId(list: string[], id: string, included: boolean): string[] {
  const s = new Set(list);
  if (included) s.delete(id);
  else s.add(id);
  return [...s];
}

function EntityCheckList({
  title,
  hint,
  entities,
  disabledIds,
  masterEnabled,
  isAdmin,
  onToggle,
  onSelectAll,
  onSelectNone,
}: {
  title: string;
  hint: string;
  entities: Array<{ id: string; name: string }>;
  disabledIds: string[];
  masterEnabled: boolean;
  isAdmin: boolean;
  onToggle: (id: string, included: boolean) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
}) {
  if (!masterEnabled || !entities.length) return null;
  const disabled = new Set(disabledIds);
  return (
    <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-slate-800">{title}</div>
          <p className="text-xs text-slate-500">{hint}</p>
        </div>
        {isAdmin ? (
          <div className="flex gap-2 text-xs">
            <button type="button" className="text-sky-700 underline" onClick={onSelectAll}>
              Все
            </button>
            <button type="button" className="text-sky-700 underline" onClick={onSelectNone}>
              Ни одного
            </button>
          </div>
        ) : null}
      </div>
      <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
        {entities.map((e) => {
          const included = !disabled.has(e.id);
          return (
            <li key={e.id}>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="rounded border-slate-300"
                  checked={included}
                  disabled={!isAdmin}
                  onChange={(ev) => onToggle(e.id, ev.target.checked)}
                />
                <span className={included ? "text-slate-800" : "text-slate-400 line-through"}>{e.name}</span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

type GeneratedReport = {
  report_config: { title: string; subtitle: string; company_name: string; company_address: string; footer_text: string };
  period: { date_from: string; date_to: string };
  ai_stats?: {
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
  indicator_telegram_sections?: import("../lib/api").IndicatorTelegramSection[];
};

type AiStepStatus = "pending" | "sending" | "receiving" | "done" | "error" | "skipped";

type AiStep = {
  stepId: string;
  title: string;
  status: AiStepStatus;
  charsIn?: number;
  charsOut?: number;
  preview?: string;
  error?: string;
};

function applyAiStreamEvent(steps: AiStep[], event: Record<string, unknown>): AiStep[] {
  const type = String(event.type || "");
  if (type === "plan" && Array.isArray(event.steps)) {
    return (event.steps as Array<{ step_id?: string; title?: string }>).map((s) => ({
      stepId: String(s.step_id || ""),
      title: String(s.title || s.step_id || ""),
      status: "pending" as const,
    }));
  }
  const stepId = String(event.step_id || "");
  if (!stepId) return steps;
  const idx = steps.findIndex((s) => s.stepId === stepId);
  const patch = (prev: AiStep): AiStep => {
    if (type === "step_send") {
      return { ...prev, status: "sending", charsIn: Number(event.chars_in) || 0 };
    }
    if (type === "step_receive") {
      const ok = event.ok !== false;
      return {
        ...prev,
        status: ok ? "done" : "error",
        charsOut: Number(event.chars_out) || 0,
        preview: event.preview ? String(event.preview) : undefined,
        error: event.error ? String(event.error) : undefined,
      };
    }
    if (type === "step_skip") {
      return { ...prev, status: "skipped" };
    }
    return prev;
  };
  if (idx >= 0) {
    const next = [...steps];
    next[idx] = patch(next[idx]);
    return next;
  }
  return [
    ...steps,
    patch({
      stepId,
      title: String(event.title || stepId),
      status: "pending",
    }),
  ];
}

type ResultTab = "general" | "competitors" | "developers" | "regions";
type GeneralSubTab = "news" | "clusters" | "indicators";
type AiFilterTab = "all" | "competitors" | "developers" | "regions" | "other";

function tabBtn(active: boolean) {
  return `shrink-0 rounded-t border px-3 py-2 text-xs font-medium transition-colors ${
    active
      ? "border-slate-300 border-b-white bg-white text-slate-900 shadow-sm"
      : "border-transparent bg-slate-100 text-slate-600 hover:bg-slate-200"
  }`;
}

function pillBtn(active: boolean) {
  return `shrink-0 rounded-full border px-2.5 py-1 text-xs ${
    active ? "border-slate-400 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
  }`;
}

function ProcessedTextBlock({
  text,
  json,
  title,
}: {
  text: string;
  json?: Record<string, unknown> | null;
  title?: string;
}) {
  return (
    <div>
      {title ? <h3 className="text-xs font-medium text-slate-600">{title}</h3> : null}
      <pre className="mt-1 max-h-[min(60vh,28rem)] overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">
        {text}
      </pre>
      {json ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-sky-700">JSON для верстки</summary>
          <pre className="mt-1 max-h-56 overflow-y-auto rounded border border-slate-200 bg-white p-2 text-xs">
            {JSON.stringify(json, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}

function EntityPickerPanel({
  entries,
  jsonByName,
  activeName,
  onPick,
  emptyLabel,
}: {
  entries: Record<string, string>;
  jsonByName: Record<string, Record<string, unknown>>;
  activeName: string;
  onPick: (name: string) => void;
  emptyLabel: string;
}) {
  const names = Object.keys(entries).sort((a, b) => a.localeCompare(b, "ru"));
  if (!names.length) {
    return <p className="text-sm text-slate-500">{emptyLabel}</p>;
  }
  const current = names.includes(activeName) ? activeName : names[0];
  const text = entries[current];
  const json = jsonByName[current];

  return (
    <div>
      <div className="-mx-1 flex gap-1 overflow-x-auto pb-2">
        {names.map((name) => (
          <button key={name} type="button" className={pillBtn(name === current)} onClick={() => onPick(name)}>
            {name}
          </button>
        ))}
      </div>
      <ProcessedTextBlock text={text} json={json} title={current} />
    </div>
  );
}

function aiStepCategory(stepId: string): AiFilterTab {
  if (stepId.startsWith("competitor:")) return "competitors";
  if (stepId.startsWith("developer:")) return "developers";
  if (stepId.startsWith("region:")) return "regions";
  return "other";
}

export function ReportConfigPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<ReportConfig>({
    title: "Аналитический отчёт",
    subtitle: "",
    company_name: "",
    company_address: "",
    footer_text: "",
    include_news: true,
    include_indicators: true,
    include_regions: true,
    include_competitors: true,
    include_developers: true,
    include_general_news: true,
    include_clusters: true,
    include_region_unassigned: true,
    disabled_competitor_ids: [],
    disabled_developer_ids: [],
    disabled_region_ids: [],
    date_range_days: 30,
    report_month: null,
    general_news_themes: DEFAULT_GENERAL_NEWS_THEMES,
  });
  const [competitors, setCompetitors] = useState<CompetitorOut[]>([]);
  const [developers, setDevelopers] = useState<DeveloperOut[]>([]);
  const [regions, setRegions] = useState<RegionOut[]>([]);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [htmlBusy, setHtmlBusy] = useState(false);
  const [publishBusy, setPublishBusy] = useState(false);
  const [generateBusy, setGenerateBusy] = useState(false);
  const [publishedItems, setPublishedItems] = useState<
    Array<{
      id: string;
      public_path: string;
      title: string;
      date_from: string;
      date_to: string;
      created_at: string;
    }>
  >([]);
  const [generated, setGenerated] = useState<GeneratedReport | null>(null);
  const [aiSteps, setAiSteps] = useState<AiStep[]>([]);
  const [aiStreamMeta, setAiStreamMeta] = useState<{ provider?: string; model?: string; total?: number } | null>(null);
  const [publishReady, setPublishReady] = useState<{ ready: boolean; message: string } | null>(null);
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [resultTab, setResultTab] = useState<ResultTab>("general");
  const [generalSubTab, setGeneralSubTab] = useState<GeneralSubTab>("news");
  const [competitorTab, setCompetitorTab] = useState("");
  const [developerTab, setDeveloperTab] = useState("");
  const [regionTab, setRegionTab] = useState("");
  const [aiFilterTab, setAiFilterTab] = useState<AiFilterTab>("all");
  const generateAbortRef = useRef<AbortController | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [c, comp, dev, reg] = await Promise.all([
        api.reportConfig.get(accessToken),
        api.competitors.list(accessToken),
        api.developers.list(accessToken),
        api.regions.list(accessToken),
      ]);
      setCompetitors(comp.items.filter((x) => x.is_active !== false));
      setDevelopers(dev.items.filter((x) => x.is_active !== false));
      setRegions(reg.items.filter((x) => x.is_active !== false));
      setForm({
        title: c.title,
        subtitle: c.subtitle,
        company_name: c.company_name,
        company_address: c.company_address,
        footer_text: c.footer_text,
        include_news: c.include_news,
        include_indicators: c.include_indicators,
        include_regions: c.include_regions,
        include_competitors: c.include_competitors ?? true,
        include_developers: c.include_developers ?? true,
        include_general_news: c.include_general_news ?? true,
        include_clusters: c.include_clusters ?? true,
        include_region_unassigned: c.include_region_unassigned ?? true,
        disabled_competitor_ids: c.disabled_competitor_ids ?? [],
        disabled_developer_ids: c.disabled_developer_ids ?? [],
        disabled_region_ids: c.disabled_region_ids ?? [],
        date_range_days: c.date_range_days,
        report_month: c.report_month ?? null,
        general_news_themes: themesFromApi(c.general_news_themes),
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const reloadPublished = async () => {
    if (!accessToken) return;
    try {
      const r = await api.reports.listPublished(accessToken, 15);
      setPublishedItems(r.items);
    } catch {
      setPublishedItems([]);
    }
  };

  useEffect(() => {
    reload();
    reloadPublished();
    return () => generateAbortRef.current?.abort();
  }, [accessToken]);

  useEffect(() => {
    if (!generated) return;
    const comp = Object.keys(generated.processed_competitors_by_name || {}).sort((a, b) => a.localeCompare(b, "ru"));
    const dev = Object.keys(generated.processed_developers_by_name || {}).sort((a, b) => a.localeCompare(b, "ru"));
    const reg = Object.keys(generated.processed_regions_by_name || {}).sort((a, b) => a.localeCompare(b, "ru"));
    setCompetitorTab(comp[0] || "");
    setDeveloperTab(dev[0] || "");
    setRegionTab(reg[0] || "");
    if (generated.processed_news) {
      setResultTab("general");
      setGeneralSubTab("news");
    } else if (generated.processed_clusters) {
      setResultTab("general");
      setGeneralSubTab("clusters");
    } else if (generated.processed_indicators) {
      setResultTab("general");
      setGeneralSubTab("indicators");
    } else if (comp.length) setResultTab("competitors");
    else if (dev.length) setResultTab("developers");
    else if (reg.length) setResultTab("regions");
  }, [generated]);

  const handleDeletePublished = async (reportId: string) => {
    if (!accessToken || !isAdmin) return;
    if (!window.confirm("Удалить опубликованный HTML-отчёт? Ссылка перестанет работать.")) return;
    setDeleteBusyId(reportId);
    try {
      await api.reports.deletePublished(accessToken, reportId);
      await reloadPublished();
      push({ variant: "success", title: "Удалено", description: "Отчёт удалён с сервера" });
    } catch (e: unknown) {
      push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось удалить" });
    } finally {
      setDeleteBusyId(null);
    }
  };

  const handleSave = async () => {
    if (!accessToken || !isAdmin) return;
    setSaveBusy(true);
    setSaveSuccess(false);
    try {
      const { general_news_themes, ...rest } = form;
      await api.reportConfig.update(accessToken, {
        ...rest,
        general_news_themes: general_news_themes.map((g) => ({
          title: g.title.trim(),
          keywords: parseThemeKeywords(g.keywords),
        })),
      });
      setSaveSuccess(true);
      reload();
      setTimeout(() => setSaveSuccess(false), 3000);
      push({ variant: "success", title: "Сохранено", description: "Настройки отчёта обновлены" });
    } catch (e: unknown) {
      push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось сохранить" });
    } finally {
      setSaveBusy(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-slate-600">Загрузка…</div>;
  }

  return (
    <div>
      <h1 className="text-lg font-semibold">Отчёт для PDF</h1>
      <p className="mt-1 text-sm text-slate-600">
        Настройки заголовка, подвала и разделов для экспорта в PDF. Данные используются при генерации отчёта.
      </p>

      <HintBox>
        <div className="font-medium">Поток данных</div>
        <div className="mt-1">
          <b>Скачать PDF (без ИИ)</b> — PDF с графиками индикаторов, новостями по регионам и каналам. <b>Сгенерировать отчёт (ИИ)</b> — данные обрабатываются ИИ; ответ включает текст для совместимости и структурированный JSON (заголовок, абзацы, тезисы со ссылками) для последующего рендера в HTML/PDF. После генерации можно нажать <b>Скачать PDF с графиками</b> — в PDF и HTML используется структура, если модель вернула валидный JSON.
        </div>
      </HintBox>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">Шапка отчёта</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="block md:col-span-2">
            <span className="text-sm text-slate-700">Заголовок</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Аналитический отчёт"
            />
          </label>
          <label className="block md:col-span-2">
            <span className="text-sm text-slate-700">Подзаголовок</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.subtitle}
              onChange={(e) => setForm((f) => ({ ...f, subtitle: e.target.value }))}
              placeholder="Опционально"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Название организации</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.company_name}
              onChange={(e) => setForm((f) => ({ ...f, company_name: e.target.value }))}
              placeholder="ООО «Компания»"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Адрес</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.company_address}
              onChange={(e) => setForm((f) => ({ ...f, company_address: e.target.value }))}
              placeholder="г. Москва, ул. Примерная, 1"
            />
          </label>
        </div>

        <h2 className="mt-6 text-sm font-semibold">Подвал</h2>
        <label className="mt-2 block">
          <span className="text-sm text-slate-700">Текст в подвале</span>
          <input
            className="mt-1 w-full rounded border px-3 py-2 text-sm"
            value={form.footer_text}
            onChange={(e) => setForm((f) => ({ ...f, footer_text: e.target.value }))}
            placeholder="Конфиденциально. Только для внутреннего использования."
          />
        </label>

        <h2 className="mt-6 text-sm font-semibold">Разделы отчёта</h2>
        <p className="mt-1 text-xs text-slate-600">
          Управляет запросами к ИИ, публикацией HTML и PDF. Снимите галочку с сущности — её блок не попадёт в отчёт.
        </p>
        <div className="mt-3 flex flex-wrap gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.include_news}
              onChange={(e) => setForm((f) => ({ ...f, include_news: e.target.checked }))}
              disabled={!isAdmin}
              className="rounded border-slate-300"
            />
            <span className="text-sm">Новости (в целом)</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.include_indicators}
              onChange={(e) => setForm((f) => ({ ...f, include_indicators: e.target.checked }))}
              disabled={!isAdmin}
              className="rounded border-slate-300"
            />
            <span className="text-sm">Индикаторы</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.include_regions}
              onChange={(e) => setForm((f) => ({ ...f, include_regions: e.target.checked }))}
              disabled={!isAdmin}
              className="rounded border-slate-300"
            />
            <span className="text-sm">Регионы</span>
          </label>
        </div>

        {form.include_news ? (
          <div className="mt-4 rounded border border-sky-100 bg-sky-50/50 p-3">
            <p className="text-xs font-medium text-sky-900">Подразделы новостей (ИИ + HTML/PDF)</p>
            <div className="mt-2 flex flex-wrap gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.include_competitors}
                  onChange={(e) => setForm((f) => ({ ...f, include_competitors: e.target.checked }))}
                  disabled={!isAdmin}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Конкуренты</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.include_developers}
                  onChange={(e) => setForm((f) => ({ ...f, include_developers: e.target.checked }))}
                  disabled={!isAdmin}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Застройщики</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.include_general_news}
                  onChange={(e) => setForm((f) => ({ ...f, include_general_news: e.target.checked }))}
                  disabled={!isAdmin}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Общие новости</span>
              </label>
              {form.include_general_news ? (
                <div className="mt-3 rounded border border-sky-100 bg-sky-50/50 p-3 sm:col-span-2 lg:col-span-3">
                  <p className="text-sm font-medium text-slate-800">Темы в «Общие новости»</p>
                  <p className="mt-1 text-xs text-slate-600">
                    Новость попадает в первую подходящую тему (по заголовку и тексту). Пустые ключи у «Прочее» — всё
                    остальное. На каждую тему — отдельный запрос к ИИ, в отчёте один блок с подзаголовками.
                  </p>
                  <div className="mt-3 space-y-3">
                    {form.general_news_themes.map((g, idx) => (
                      <div
                        key={idx}
                        className="grid grid-cols-1 gap-2 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-2"
                      >
                        <label className="block">
                          <span className="text-xs text-slate-600">Тема</span>
                          <input
                            className="mt-1 w-full rounded border px-3 py-2 text-sm"
                            value={g.title}
                            disabled={!isAdmin}
                            onChange={(e) =>
                              setForm((f) => {
                                const themes = [...f.general_news_themes];
                                themes[idx] = { ...themes[idx], title: e.target.value };
                                return { ...f, general_news_themes: themes };
                              })
                            }
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-slate-600">Ключи (через запятую)</span>
                          <textarea
                            className="mt-1 w-full rounded border px-3 py-2 text-sm"
                            rows={2}
                            value={g.keywords}
                            disabled={!isAdmin}
                            placeholder="Пусто — только для «Прочее»"
                            onChange={(e) =>
                              setForm((f) => {
                                const themes = [...f.general_news_themes];
                                themes[idx] = { ...themes[idx], keywords: e.target.value };
                                return { ...f, general_news_themes: themes };
                              })
                            }
                          />
                        </label>
                      </div>
                    ))}
                  </div>
                  {isAdmin ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="rounded border bg-white px-2 py-1 text-xs hover:bg-slate-50"
                        onClick={() =>
                          setForm((f) => ({
                            ...f,
                            general_news_themes: [...f.general_news_themes, { title: "Новая тема", keywords: "" }],
                          }))
                        }
                      >
                        + Тема
                      </button>
                      <button
                        type="button"
                        className="rounded border bg-white px-2 py-1 text-xs hover:bg-slate-50"
                        onClick={() => setForm((f) => ({ ...f, general_news_themes: DEFAULT_GENERAL_NEWS_THEMES }))}
                      >
                        Сбросить к умолчанию
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.include_clusters}
                  onChange={(e) => setForm((f) => ({ ...f, include_clusters: e.target.checked }))}
                  disabled={!isAdmin}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Кластеры</span>
              </label>
            </div>
            <EntityCheckList
              title="Конкуренты в отчёте"
              hint="Снятая галочка — без саммари ИИ и без блока в HTML/PDF"
              entities={competitors.map((c) => ({ id: c.id, name: c.name }))}
              disabledIds={form.disabled_competitor_ids}
              masterEnabled={form.include_competitors}
              isAdmin={isAdmin}
              onToggle={(id, included) =>
                setForm((f) => ({ ...f, disabled_competitor_ids: toggleId(f.disabled_competitor_ids, id, included) }))
              }
              onSelectAll={() => setForm((f) => ({ ...f, disabled_competitor_ids: [] }))}
              onSelectNone={() =>
                setForm((f) => ({ ...f, disabled_competitor_ids: competitors.map((c) => c.id) }))
              }
            />
            <EntityCheckList
              title="Застройщики в отчёте"
              hint="Снятая галочка — раздел скрыт"
              entities={developers.map((d) => ({ id: d.id, name: d.name }))}
              disabledIds={form.disabled_developer_ids}
              masterEnabled={form.include_developers}
              isAdmin={isAdmin}
              onToggle={(id, included) =>
                setForm((f) => ({ ...f, disabled_developer_ids: toggleId(f.disabled_developer_ids, id, included) }))
              }
              onSelectAll={() => setForm((f) => ({ ...f, disabled_developer_ids: [] }))}
              onSelectNone={() =>
                setForm((f) => ({ ...f, disabled_developer_ids: developers.map((d) => d.id) }))
              }
            />
          </div>
        ) : null}

        {form.include_regions ? (
          <div className="mt-4 rounded border border-violet-100 bg-violet-50/40 p-3">
            <label className="mb-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.include_region_unassigned}
                onChange={(e) => setForm((f) => ({ ...f, include_region_unassigned: e.target.checked }))}
                disabled={!isAdmin}
                className="rounded border-slate-300"
              />
              <span className="text-sm">Включать «Без региона»</span>
            </label>
            <EntityCheckList
              title="Регионы в отчёте"
              hint="Отключённые регионы не отправляются в ИИ"
              entities={regions.map((r) => ({ id: r.id, name: r.name }))}
              disabledIds={form.disabled_region_ids}
              masterEnabled
              isAdmin={isAdmin}
              onToggle={(id, included) =>
                setForm((f) => ({ ...f, disabled_region_ids: toggleId(f.disabled_region_ids, id, included) }))
              }
              onSelectAll={() => setForm((f) => ({ ...f, disabled_region_ids: [] }))}
              onSelectNone={() => setForm((f) => ({ ...f, disabled_region_ids: regions.map((r) => r.id) }))}
            />
          </div>
        ) : null}
        <label className="mt-3 block">
          <span className="text-sm text-slate-700">Месяц отчёта (YYYY-MM)</span>
          <input
            type="month"
            className="mt-1 w-40 rounded border px-3 py-2 text-sm"
            value={form.report_month || ""}
            onChange={(e) => setForm((f) => ({ ...f, report_month: e.target.value || null }))}
            disabled={!isAdmin}
          />
          <p className="mt-1 text-xs text-slate-500">Приоритет: только новости этого месяца попадают в отчёт</p>
        </label>
        <label className="mt-3 block">
          <span className="text-sm text-slate-700">Период по умолчанию (дней)</span>
          <input
            type="number"
            min={1}
            max={365}
            className="mt-1 w-24 rounded border px-3 py-2 text-sm"
            value={form.date_range_days}
            onChange={(e) => setForm((f) => ({ ...f, date_range_days: parseInt(e.target.value, 10) || 30 }))}
            disabled={!isAdmin}
          />
          <p className="mt-1 text-xs text-slate-500">Используется, если месяц не задан</p>
        </label>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <button
            className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
            onClick={handleSave}
            disabled={saveBusy || !isAdmin}
          >
            <Save className="h-4 w-4" />
            Сохранить
          </button>
          <button
            className="inline-flex items-center gap-2 rounded bg-emerald-600 px-3 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
            onClick={async () => {
              if (!accessToken) return;
              setPdfBusy(true);
              try {
                const blob = await api.reports.generatePdf(accessToken, {
                  date_range_days: form.date_range_days,
                  report_month: form.report_month || undefined,
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `report_${form.report_month || "period"}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
                push({ variant: "success", title: "PDF", description: "Отчёт скачан" });
              } catch (e: unknown) {
                push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось скачать PDF" });
              } finally {
                setPdfBusy(false);
              }
            }}
            disabled={pdfBusy || generateBusy}
          >
            {pdfBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Скачать PDF (без ИИ)
          </button>
          <button
            className="inline-flex items-center gap-2 rounded bg-sky-600 px-3 py-2 text-sm text-white hover:bg-sky-700 disabled:opacity-50"
            onClick={async () => {
              if (!accessToken) return;
              setHtmlBusy(true);
              try {
                const blob = await api.reports.generateHtml(accessToken, {
                  date_range_days: form.date_range_days,
                  report_month: form.report_month || undefined,
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `report_${form.report_month || "period"}.html`;
                a.click();
                URL.revokeObjectURL(url);
                push({ variant: "success", title: "HTML", description: "HTML-отчёт скачан" });
              } catch (e: unknown) {
                push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось скачать HTML" });
              } finally {
                setHtmlBusy(false);
              }
            }}
            disabled={htmlBusy || pdfBusy || generateBusy}
          >
            {htmlBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Скачать HTML (современный)
          </button>
          <button
            className="inline-flex items-center gap-2 rounded bg-violet-600 px-3 py-2 text-sm text-white hover:bg-violet-700 disabled:opacity-50"
            onClick={async () => {
              if (!accessToken) return;
              setPublishBusy(true);
              try {
                const useCachedAi = Boolean(generated);
                const meta = await api.reports.publishHtml(accessToken, {
                  date_range_days: form.date_range_days,
                  report_month: form.report_month || undefined,
                  ...(generated
                    ? {
                        date_from: generated.period.date_from,
                        date_to: generated.period.date_to,
                        skip_ai: true,
                        processed_indicators: generated.processed_indicators ?? undefined,
                        processed_news: generated.processed_news ?? undefined,
                        processed_clusters: generated.processed_clusters ?? undefined,
                        processed_news_json: generated.processed_news_json ?? undefined,
                        processed_indicators_json: generated.processed_indicators_json ?? undefined,
                        processed_clusters_json: generated.processed_clusters_json ?? undefined,
                        processed_competitors_by_name: generated.processed_competitors_by_name,
                        processed_developers_by_name: generated.processed_developers_by_name,
                        processed_regions_by_name: generated.processed_regions_by_name,
                        processed_competitors_by_name_json: generated.processed_competitors_by_name_json,
                        processed_developers_by_name_json: generated.processed_developers_by_name_json,
                        processed_regions_by_name_json: generated.processed_regions_by_name_json,
                        indicator_telegram_sections: generated.indicator_telegram_sections,
                      }
                    : {}),
                });
                const url = `${window.location.origin}${meta.public_path}`;
                await reloadPublished();
                push({
                  variant: "success",
                  title: "HTML опубликован",
                  description: useCachedAi ? `${url} (без повторного ИИ)` : url,
                });
                window.open(url, "_blank", "noopener,noreferrer");
              } catch (e: unknown) {
                push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось опубликовать" });
              } finally {
                setPublishBusy(false);
              }
            }}
            disabled={publishBusy || htmlBusy || pdfBusy || generateBusy}
          >
            {publishBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Опубликовать HTML (ссылка)
          </button>
          <p className="w-full text-xs text-slate-500">
            Сначала «Сгенерировать отчёт (ИИ)», затем публикация — быстрее (ИИ не вызывается повторно). Без генерации публикация займёт несколько минут.
          </p>
          <span className="text-slate-400">|</span>
          <button
            className="inline-flex items-center gap-2 rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            onClick={async () => {
              if (!accessToken) return;
              generateAbortRef.current?.abort();
              const ac = new AbortController();
              generateAbortRef.current = ac;
              setGenerateBusy(true);
              setGenerated(null);
              setAiSteps([]);
              setAiStreamMeta(null);
              setPublishReady(null);
              setAiFilterTab("all");
              try {
                const r = (await api.reports.generateStream(
                  accessToken,
                  {
                    date_range_days: form.date_range_days,
                    report_month: form.report_month || undefined,
                  },
                  (ev) => {
                    if (ev.type === "plan") {
                      setAiStreamMeta({
                        provider: ev.provider ? String(ev.provider) : undefined,
                        model: ev.model ? String(ev.model) : undefined,
                        total: Number(ev.total_steps) || undefined,
                      });
                    }
                    if (ev.type === "ready") {
                      setPublishReady({
                        ready: ev.ready !== false,
                        message: String(ev.message || "Готово к публикации"),
                      });
                    }
                    setAiSteps((prev) => applyAiStreamEvent(prev, ev));
                  },
                  ac.signal,
                )) as GeneratedReport;
                setGenerated(r);
                push({ variant: "success", title: "Готово", description: "Данные обработаны ИИ" });
              } catch (e: unknown) {
                if (e instanceof Error && e.name === "AbortError") return;
                push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось сгенерировать" });
              } finally {
                setGenerateBusy(false);
              }
            }}
            disabled={pdfBusy || generateBusy}
          >
            {generateBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Сгенерировать отчёт (ИИ)
          </button>
          {saveSuccess ? <span className="text-sm text-emerald-600">Сохранено</span> : null}
        </div>

        {(generateBusy || aiSteps.length > 0) ? (
          <div className="mt-4 rounded border border-slate-200 bg-slate-50 p-3">
            <h3 className="text-sm font-semibold text-slate-800">Обмен данными с ИИ</h3>
            {aiStreamMeta ? (
              <p className="mt-1 text-xs text-slate-600">
                {aiStreamMeta.provider || "—"} / {aiStreamMeta.model || "—"}
                {aiStreamMeta.total != null ? ` · шагов: ${aiStreamMeta.total}` : null}
              </p>
            ) : null}
            {aiSteps.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1 border-b border-slate-200 pb-2">
                {(
                  [
                    ["all", "Все", aiSteps.length],
                    ["competitors", "Конкуренты", aiSteps.filter((s) => aiStepCategory(s.stepId) === "competitors").length],
                    ["developers", "Застройщики", aiSteps.filter((s) => aiStepCategory(s.stepId) === "developers").length],
                    ["regions", "Регионы", aiSteps.filter((s) => aiStepCategory(s.stepId) === "regions").length],
                    ["other", "Прочее", aiSteps.filter((s) => aiStepCategory(s.stepId) === "other").length],
                  ] as const
                )
                  .filter(([id, , n]) => id === "all" || n > 0)
                  .map(([id, label, n]) => (
                    <button
                      key={id}
                      type="button"
                      className={pillBtn(aiFilterTab === id)}
                      onClick={() => setAiFilterTab(id)}
                    >
                      {label}
                      {id !== "all" ? ` (${n})` : ""}
                    </button>
                  ))}
              </div>
            ) : null}
            <ul className="mt-2 max-h-[min(50vh,24rem)] space-y-2 overflow-y-auto">
              {aiSteps
                .filter((step) => aiFilterTab === "all" || aiStepCategory(step.stepId) === aiFilterTab)
                .map((step) => (
                <li key={step.stepId} className="rounded border bg-white px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    {step.status === "sending" ? (
                      <ArrowUpRight className="h-4 w-4 shrink-0 text-sky-600" aria-hidden />
                    ) : step.status === "done" ? (
                      <ArrowDownLeft className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                    ) : step.status === "error" ? (
                      <XCircle className="h-4 w-4 shrink-0 text-red-600" aria-hidden />
                    ) : step.status === "skipped" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                    ) : (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-slate-400" aria-hidden />
                    )}
                    <span className="font-medium">{step.title}</span>
                    <span className="text-xs text-slate-500">
                      {step.status === "pending" && "ожидание"}
                      {step.status === "sending" && "отправка в ИИ…"}
                      {step.status === "receiving" && "получение ответа…"}
                      {step.status === "done" && "получено"}
                      {step.status === "error" && "ошибка"}
                      {step.status === "skipped" && "пропущено"}
                    </span>
                  </div>
                  {(step.charsIn != null && step.charsIn > 0) || (step.charsOut != null && step.charsOut > 0) ? (
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-600">
                      {step.charsIn != null && step.charsIn > 0 ? (
                        <span className="inline-flex items-center gap-1">
                          <ArrowUpRight className="h-3 w-3 text-sky-600" />
                          в ИИ: {step.charsIn.toLocaleString("ru-RU")} симв.
                        </span>
                      ) : null}
                      {step.charsOut != null && step.charsOut > 0 ? (
                        <span className="inline-flex items-center gap-1">
                          <ArrowDownLeft className="h-3 w-3 text-emerald-600" />
                          от ИИ: {step.charsOut.toLocaleString("ru-RU")} симв.
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {step.preview ? (
                    <p className="mt-1 line-clamp-2 text-xs text-slate-600">{step.preview}</p>
                  ) : null}
                  {step.error ? <p className="mt-1 text-xs text-red-700">{step.error}</p> : null}
                </li>
              ))}
            </ul>
            {generateBusy && aiSteps.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">Сбор данных и план запросов к ИИ…</p>
            ) : null}
          </div>
        ) : null}

        {publishReady && generated && !generateBusy ? (
          <div
            className={`mt-4 rounded-lg border-2 p-4 ${
              publishReady.ready ? "border-emerald-500 bg-emerald-50" : "border-amber-400 bg-amber-50"
            }`}
          >
            <div className="flex flex-wrap items-start gap-3">
              <CheckCircle2
                className={`h-6 w-6 shrink-0 ${publishReady.ready ? "text-emerald-700" : "text-amber-700"}`}
              />
              <div className="min-w-0 flex-1">
                <p className={`font-semibold ${publishReady.ready ? "text-emerald-900" : "text-amber-900"}`}>
                  {publishReady.ready ? "Готово к публикации" : "Публикация с предупреждением"}
                </p>
                <p className={`mt-1 text-sm ${publishReady.ready ? "text-emerald-800" : "text-amber-800"}`}>
                  {publishReady.message}
                </p>
                <p className={`mt-1 text-xs ${publishReady.ready ? "text-emerald-700" : "text-amber-700"}`}>
                  Период: {generated.period.date_from} — {generated.period.date_to}. Публикация HTML без повторных запросов к ИИ.
                </p>
              </div>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded bg-violet-700 px-4 py-2 text-sm font-medium text-white hover:bg-violet-800 disabled:opacity-50"
                disabled={publishBusy}
                onClick={async () => {
                  if (!accessToken || !generated) return;
                  setPublishBusy(true);
                  try {
                    const meta = await api.reports.publishHtml(accessToken, {
                      date_from: generated.period.date_from,
                      date_to: generated.period.date_to,
                      report_month: form.report_month || undefined,
                      skip_ai: true,
                      processed_indicators: generated.processed_indicators ?? undefined,
                      processed_news: generated.processed_news ?? undefined,
                      processed_clusters: generated.processed_clusters ?? undefined,
                      processed_news_json: generated.processed_news_json ?? undefined,
                      processed_indicators_json: generated.processed_indicators_json ?? undefined,
                      processed_clusters_json: generated.processed_clusters_json ?? undefined,
                      processed_competitors_by_name: generated.processed_competitors_by_name,
                      processed_developers_by_name: generated.processed_developers_by_name,
                      processed_regions_by_name: generated.processed_regions_by_name,
                      processed_competitors_by_name_json: generated.processed_competitors_by_name_json,
                      processed_developers_by_name_json: generated.processed_developers_by_name_json,
                      processed_regions_by_name_json: generated.processed_regions_by_name_json,
                      indicator_telegram_sections: generated.indicator_telegram_sections,
                    });
                    const url = `${window.location.origin}${meta.public_path}`;
                    await reloadPublished();
                    push({ variant: "success", title: "HTML опубликован", description: url });
                    window.open(url, "_blank", "noopener,noreferrer");
                  } catch (e: unknown) {
                    push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось опубликовать" });
                  } finally {
                    setPublishBusy(false);
                  }
                }}
              >
                {publishBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                Опубликовать HTML-страницу
              </button>
            </div>
          </div>
        ) : null}

        {!isAdmin ? (
          <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
            Редактирование доступно только роли Admin.
          </div>
        ) : null}
      </div>

      {publishedItems.length > 0 ? (
        <div className="mt-4 rounded border bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Опубликованные HTML-отчёты</h2>
          <p className="mt-1 text-xs text-slate-500">Доступны по адресу от корня сайта: /reports/…</p>
          <ul className="mt-2 space-y-2 text-sm">
            {publishedItems.map((item) => {
              const href = `${window.location.origin}${item.public_path}`;
              return (
                <li key={item.id} className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2 first:border-0 first:pt-0">
                  <span className="font-medium">{item.title}</span>
                  <span className="text-slate-500">
                    {item.date_from} — {item.date_to}
                  </span>
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-sky-700 underline">
                    {item.public_path}
                  </a>
                  {isAdmin ? (
                    <button
                      type="button"
                      className="ml-auto inline-flex items-center gap-1 rounded border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                      disabled={deleteBusyId === item.id}
                      onClick={() => handleDeletePublished(item.id)}
                      title="Удалить отчёт"
                    >
                      {deleteBusyId === item.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Trash2 className="h-3 w-3" />
                      )}
                      Удалить
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {generated ? (
        <div className="mt-6 rounded border bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Обработанные данные за {generated.period.date_from} — {generated.period.date_to}</h2>
            <button
              className="inline-flex items-center gap-2 rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
              onClick={async () => {
                if (!accessToken) return;
                setPdfBusy(true);
                try {
                  const blob = await api.reports.generatePdf(accessToken, {
                    date_from: generated!.period.date_from,
                    date_to: generated!.period.date_to,
                    processed_indicators: generated!.processed_indicators ?? undefined,
                    processed_news: generated!.processed_news ?? undefined,
                    processed_clusters: generated!.processed_clusters ?? undefined,
                    processed_competitors_by_name: generated!.processed_competitors_by_name,
                    processed_developers_by_name: generated!.processed_developers_by_name,
                    processed_regions_by_name: generated!.processed_regions_by_name,
                    processed_news_json: generated!.processed_news_json ?? undefined,
                    processed_indicators_json: generated!.processed_indicators_json ?? undefined,
                    processed_clusters_json: generated!.processed_clusters_json ?? undefined,
                    processed_competitors_by_name_json: generated!.processed_competitors_by_name_json,
                    processed_developers_by_name_json: generated!.processed_developers_by_name_json,
                    processed_regions_by_name_json: generated!.processed_regions_by_name_json,
                    indicator_telegram_sections: generated!.indicator_telegram_sections,
                  });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `report_${generated!.period.date_from}_${generated!.period.date_to}.pdf`;
                  a.click();
                  URL.revokeObjectURL(url);
                  push({ variant: "success", title: "PDF", description: "Отчёт с графиками скачан" });
                } catch (e: unknown) {
                  push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось скачать PDF" });
                } finally {
                  setPdfBusy(false);
                }
              }}
              disabled={pdfBusy}
            >
              {pdfBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              Скачать PDF с графиками
            </button>
          </div>
          {generated.ai_stats ? (
            <div
              className={`mt-3 rounded border p-2 text-xs ${
                (generated.ai_stats.failed ?? 0) > 0 ? "border-amber-200 bg-amber-50 text-amber-900" : "border-slate-200 bg-slate-50 text-slate-700"
              }`}
            >
              ИИ: запросов {generated.ai_stats.calls}, успешно {generated.ai_stats.succeeded}, ошибок {generated.ai_stats.failed}.
              Пауза между запросами: {generated.ai_stats.request_delay_seconds} с.
              {(generated.ai_stats.labels_failed?.length ?? 0) > 0 ? (
                <span className="block mt-1">Сбои: {generated.ai_stats.labels_failed.join(", ")}</span>
              ) : null}
            </div>
          ) : null}
          {(() => {
            const g = generated;
            const compCount = Object.keys(g.processed_competitors_by_name || {}).length;
            const devCount = Object.keys(g.processed_developers_by_name || {}).length;
            const regCount = Object.keys(g.processed_regions_by_name || {}).length;
            const hasGeneral = Boolean(g.processed_news || g.processed_clusters || g.processed_indicators);

            return (
              <div className="mt-3">
                <div className="flex flex-wrap gap-0.5 border-b border-slate-200">
                  {hasGeneral ? (
                    <button type="button" className={tabBtn(resultTab === "general")} onClick={() => setResultTab("general")}>
                      Общее
                    </button>
                  ) : null}
                  {compCount > 0 ? (
                    <button type="button" className={tabBtn(resultTab === "competitors")} onClick={() => setResultTab("competitors")}>
                      Конкуренты ({compCount})
                    </button>
                  ) : null}
                  {devCount > 0 ? (
                    <button type="button" className={tabBtn(resultTab === "developers")} onClick={() => setResultTab("developers")}>
                      Застройщики ({devCount})
                    </button>
                  ) : null}
                  {regCount > 0 ? (
                    <button type="button" className={tabBtn(resultTab === "regions")} onClick={() => setResultTab("regions")}>
                      Регионы ({regCount})
                    </button>
                  ) : null}
                </div>
                <div className="rounded-b border border-t-0 border-slate-200 bg-white p-3">
                  {resultTab === "general" && hasGeneral ? (
                    <div>
                      <div className="mb-3 flex flex-wrap gap-1">
                        {g.processed_news ? (
                          <button type="button" className={pillBtn(generalSubTab === "news")} onClick={() => setGeneralSubTab("news")}>
                            Новости
                          </button>
                        ) : null}
                        {g.processed_clusters ? (
                          <button
                            type="button"
                            className={pillBtn(generalSubTab === "clusters")}
                            onClick={() => setGeneralSubTab("clusters")}
                          >
                            Кластеры
                          </button>
                        ) : null}
                        {g.processed_indicators ? (
                          <button
                            type="button"
                            className={pillBtn(generalSubTab === "indicators")}
                            onClick={() => setGeneralSubTab("indicators")}
                          >
                            Индикаторы
                          </button>
                        ) : null}
                      </div>
                      {generalSubTab === "news" && g.processed_news ? (
                        <ProcessedTextBlock
                          title="Общие новости (ИИ)"
                          text={g.processed_news}
                          json={g.processed_news_json}
                        />
                      ) : null}
                      {generalSubTab === "clusters" && g.processed_clusters ? (
                        <ProcessedTextBlock
                          title="Кластеры похожих новостей (ИИ)"
                          text={g.processed_clusters}
                          json={g.processed_clusters_json}
                        />
                      ) : null}
                      {generalSubTab === "indicators" && g.processed_indicators ? (
                        <ProcessedTextBlock
                          title="Индикаторы (ИИ)"
                          text={g.processed_indicators}
                          json={g.processed_indicators_json}
                        />
                      ) : null}
                    </div>
                  ) : null}
                  {resultTab === "competitors" && compCount > 0 ? (
                    <EntityPickerPanel
                      entries={g.processed_competitors_by_name}
                      jsonByName={g.processed_competitors_by_name_json ?? {}}
                      activeName={competitorTab}
                      onPick={setCompetitorTab}
                      emptyLabel="Нет саммари по конкурентам"
                    />
                  ) : null}
                  {resultTab === "developers" && devCount > 0 ? (
                    <EntityPickerPanel
                      entries={g.processed_developers_by_name}
                      jsonByName={g.processed_developers_by_name_json ?? {}}
                      activeName={developerTab}
                      onPick={setDeveloperTab}
                      emptyLabel="Нет саммари по застройщикам"
                    />
                  ) : null}
                  {resultTab === "regions" && regCount > 0 ? (
                    <EntityPickerPanel
                      entries={g.processed_regions_by_name}
                      jsonByName={g.processed_regions_by_name_json ?? {}}
                      activeName={regionTab}
                      onPick={setRegionTab}
                      emptyLabel="Нет саммари по регионам"
                    />
                  ) : null}
                </div>
              </div>
            );
          })()}
        </div>
      ) : null}
    </div>
  );
}
