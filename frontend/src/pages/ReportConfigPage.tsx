import { useEffect, useState } from "react";
import { FileText, Loader2, Save } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

type ReportConfig = {
  title: string;
  subtitle: string;
  company_name: string;
  company_address: string;
  footer_text: string;
  include_news: boolean;
  include_indicators: boolean;
  include_regions: boolean;
  date_range_days: number;
  report_month: string | null;
};

export function ReportConfigPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";

  const [config, setConfig] = useState<ReportConfig | null>(null);
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
    date_range_days: 30,
    report_month: null,
  });
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
  const [generated, setGenerated] = useState<{
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
  } | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const c = await api.reportConfig.get(accessToken);
      setConfig(c);
      setForm({
        title: c.title,
        subtitle: c.subtitle,
        company_name: c.company_name,
        company_address: c.company_address,
        footer_text: c.footer_text,
        include_news: c.include_news,
        include_indicators: c.include_indicators,
        include_regions: c.include_regions,
        date_range_days: c.date_range_days,
        report_month: c.report_month ?? null,
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
  }, [accessToken]);

  const handleSave = async () => {
    if (!accessToken || !isAdmin) return;
    setSaveBusy(true);
    setSaveSuccess(false);
    try {
      await api.reportConfig.update(accessToken, form);
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
        <p className="mt-1 text-xs text-slate-600">Какие блоки включать в PDF.</p>
        <div className="mt-3 flex flex-wrap gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.include_news}
              onChange={(e) => setForm((f) => ({ ...f, include_news: e.target.checked }))}
              disabled={!isAdmin}
              className="rounded border-slate-300"
            />
            <span className="text-sm">Новости</span>
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
                const meta = await api.reports.publishHtml(accessToken, {
                  date_range_days: form.date_range_days,
                  report_month: form.report_month || undefined,
                });
                const url = `${window.location.origin}${meta.public_path}`;
                await reloadPublished();
                push({
                  variant: "success",
                  title: "HTML опубликован",
                  description: url,
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
          <span className="text-slate-400">|</span>
          <button
            className="inline-flex items-center gap-2 rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            onClick={async () => {
              if (!accessToken) return;
              setGenerateBusy(true);
              setGenerated(null);
              try {
                const r = await api.reports.generate(accessToken, {
                  date_range_days: form.date_range_days,
                  report_month: form.report_month || undefined,
                });
                setGenerated(r);
                push({ variant: "success", title: "Готово", description: "Данные обработаны ИИ" });
              } catch (e: unknown) {
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
          <div className="mt-3 space-y-4">
            {generated.processed_news ? (
              <div>
                <h3 className="text-xs font-medium text-slate-600">Общие новости (ИИ)</h3>
                <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{generated.processed_news}</pre>
                {generated.processed_news_json ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-sky-700">JSON для верстки / внешних пайплайнов</summary>
                    <pre className="mt-1 max-h-56 overflow-y-auto rounded border border-slate-200 bg-white p-2 text-xs">{JSON.stringify(generated.processed_news_json, null, 2)}</pre>
                  </details>
                ) : null}
              </div>
            ) : null}
            {generated.processed_clusters ? (
              <div>
                <h3 className="text-xs font-medium text-slate-600">Кластеры похожих новостей (ИИ)</h3>
                <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{generated.processed_clusters}</pre>
                {generated.processed_clusters_json ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-sky-700">JSON для верстки</summary>
                    <pre className="mt-1 max-h-56 overflow-y-auto rounded border border-slate-200 bg-white p-2 text-xs">{JSON.stringify(generated.processed_clusters_json, null, 2)}</pre>
                  </details>
                ) : null}
              </div>
            ) : null}
            {generated.processed_indicators ? (
              <div>
                <h3 className="text-xs font-medium text-slate-600">Индикаторы (ИИ)</h3>
                <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{generated.processed_indicators}</pre>
                {generated.processed_indicators_json ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-sky-700">JSON для верстки</summary>
                    <pre className="mt-1 max-h-56 overflow-y-auto rounded border border-slate-200 bg-white p-2 text-xs">{JSON.stringify(generated.processed_indicators_json, null, 2)}</pre>
                  </details>
                ) : null}
              </div>
            ) : null}
            {Object.keys(generated.processed_developers_by_name || {}).length > 0 ? (
              <div>
                <h3 className="text-xs font-medium text-slate-600">Застройщики (ИИ)</h3>
                <div className="mt-1 space-y-2">
                  {Object.entries(generated.processed_developers_by_name).map(([name, text]) => (
                    <div key={name}>
                      <div className="text-xs font-semibold text-slate-700">{name}</div>
                      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{text}</pre>
                      {(generated.processed_developers_by_name_json ?? {})[name] ? (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-xs text-sky-700">JSON</summary>
                          <pre className="mt-1 max-h-40 overflow-y-auto rounded border bg-white p-2 text-xs">
                            {JSON.stringify((generated.processed_developers_by_name_json ?? {})[name], null, 2)}
                          </pre>
                        </details>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {Object.keys(generated.processed_competitors_by_name || {}).length > 0 ? (
              <div>
                <h3 className="text-xs font-medium text-slate-600">Саммари по конкурентам</h3>
                <div className="mt-1 space-y-2">
                  {Object.entries(generated.processed_competitors_by_name).map(([name, text]) => (
                    <div key={name}>
                      <div className="text-xs font-semibold text-slate-700">{name}</div>
                      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{text}</pre>
                      {(generated.processed_competitors_by_name_json ?? {})[name] ? (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-xs text-sky-700">JSON</summary>
                          <pre className="mt-1 max-h-40 overflow-y-auto rounded border bg-white p-2 text-xs">
                            {JSON.stringify((generated.processed_competitors_by_name_json ?? {})[name], null, 2)}
                          </pre>
                        </details>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {Object.keys(generated.processed_regions_by_name || {}).length > 0 ? (
              <div>
                <h3 className="text-xs font-medium text-slate-600">Саммари по регионам</h3>
                <div className="mt-1 space-y-2">
                  {Object.entries(generated.processed_regions_by_name).map(([name, text]) => (
                    <div key={name}>
                      <div className="text-xs font-semibold text-slate-700">{name}</div>
                      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{text}</pre>
                      {(generated.processed_regions_by_name_json ?? {})[name] ? (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-xs text-sky-700">JSON</summary>
                          <pre className="mt-1 max-h-40 overflow-y-auto rounded border bg-white p-2 text-xs">
                            {JSON.stringify((generated.processed_regions_by_name_json ?? {})[name], null, 2)}
                          </pre>
                        </details>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
