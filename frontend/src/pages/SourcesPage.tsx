import { useEffect, useMemo, useState } from "react";
import { api, type CompetitorOut, type ParsingTemplateOut, type RegionOut, type SourceOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HelpText, HintBox, InstructionBox } from "../components/Field";

type SourceForm = {
  source_type: string;
  name: string;
  base_url: string;
  feed_url: string;
  tg_channel_username: string;
  competitor_id: string;
  region_tags: string[];
  enabled: boolean;
  fetch_frequency_min: number;
  priority: number;
  delay_ms: number;
  max_requests_per_minute: number;
  retries: number;
  respect_robots_txt: boolean;
  parsing_template_id: string;
  include_keywords: string;
  exclude_keywords: string;
  settings_json_text: string;
};

function prettyJson(v: any) {
  return JSON.stringify(v ?? {}, null, 2);
}

function parseKeywords(s: string): string[] {
  return s
    .split(/[\n,;]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function toForm(s?: SourceOut): SourceForm {
  const settings = (s?.settings_json ?? {}) as Record<string, unknown>;
  const include = (settings.include_keywords as string[] | undefined) ?? [];
  const exclude = (settings.exclude_keywords as string[] | undefined) ?? [];
  const rest = { ...settings };
  delete rest.include_keywords;
  delete rest.exclude_keywords;

  return {
    source_type: s?.source_type ?? "RSS_ATOM",
    name: (s?.name ?? "") as string,
    base_url: (s?.base_url ?? "") as string,
    feed_url: (s?.feed_url ?? "") as string,
    tg_channel_username: (s?.tg_channel_username ?? "") as string,
    competitor_id: (s?.competitor_id ?? "") as string,
    region_tags: s?.region_tags ?? [],
    enabled: s?.enabled ?? true,
    fetch_frequency_min: s?.fetch_frequency_min ?? 60,
    priority: s?.priority ?? 0,
    delay_ms: s?.delay_ms ?? 0,
    max_requests_per_minute: s?.max_requests_per_minute ?? 60,
    retries: s?.retries ?? 3,
    respect_robots_txt: s?.respect_robots_txt ?? false,
    parsing_template_id: (s?.parsing_template_id ?? "") as string,
    include_keywords: Array.isArray(include) ? include.join("\n") : "",
    exclude_keywords: Array.isArray(exclude) ? exclude.join("\n") : "",
    settings_json_text: prettyJson(rest),
  };
}

export function SourcesPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";
  const canWrite = isAdmin;

  const [items, setItems] = useState<SourceOut[]>([]);
  const [regions, setRegions] = useState<RegionOut[]>([]);
  const [competitors, setCompetitors] = useState<CompetitorOut[]>([]);
  const [templates, setTemplates] = useState<ParsingTemplateOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SourceOut | null>(null);
  const [form, setForm] = useState<SourceForm>(() => toForm());

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [s, r, c, t] = await Promise.all([
        api.sources.list(accessToken),
        api.regions.list(accessToken),
        api.competitors.list(accessToken),
        api.parsingTemplates.list(accessToken),
      ]);
      setItems(s.items);
      setRegions(r.items);
      setCompetitors(c.items);
      setTemplates(t.items);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const templateById = useMemo(() => new Map(templates.map((t) => [t.id, `${t.name} v${t.version}`])), [templates]);
  const competitorById = useMemo(() => new Map(competitors.map((c) => [c.id, c.name])), [competitors]);
  const regionById = useMemo(() => new Map(regions.map((r) => [r.id, r.name])), [regions]);

  const isRss = form.source_type === "RSS_ATOM";
  const isTelegram = form.source_type === "TELEGRAM_CHANNEL";
  const isSitemap = form.source_type === "SITEMAP";
  const isHtml = form.source_type === "HTML_LIST_DETAIL" || form.source_type === "HTML_DETAIL_ONLY" || isSitemap;
  const needsTemplate = form.source_type === "HTML_LIST_DETAIL" || form.source_type === "HTML_DETAIL_ONLY";

  const typeInstructions = (
    <InstructionBox title={`Инструкция: ${form.source_type}`}>
      {isRss ? (
        <div className="space-y-2">
          <div className="font-medium">Для чего</div>
          <div>Подходит, когда сайт публикует RSS/Atom. Самый стабильный и “дешёвый” способ сбора.</div>

          <div className="font-medium">Что заполнить</div>
          <ul className="list-disc pl-4">
            <li>
              <b>feed_url</b> — ссылка на RSS/Atom, например: <code>https://site.ru/rss.xml</code>
            </li>
            <li>
              (Опционально) <b>Конкурент</b> — если это источник конкурента, чтобы попадал в конкурентные страницы отчёта
            </li>
            <li>
              (Опционально) <b>Регионы</b> — если фид региональный/локальный
            </li>
          </ul>

          <div className="font-medium">Как работает</div>
          <ul className="list-disc pl-4">
            <li>Используем conditional GET (ETag/Last-Modified), чтобы не скачивать одно и то же.</li>
            <li>Берём title/link/date/summary; fulltext — если есть (настроим позже через RSS settings).</li>
          </ul>

          <div className="font-medium">Частые ошибки</div>
          <ul className="list-disc pl-4">
            <li>Подставляют HTML‑страницу раздела вместо RSS.</li>
            <li>Фид отдаёт редиректы — проверьте, что конечный URL открывается.</li>
          </ul>
        </div>
      ) : null}

      {form.source_type === "HTML_LIST_DETAIL" ? (
        <div className="space-y-2">
          <div className="font-medium">Для чего</div>
          <div>Сайты без RSS. Мы ходим на страницу списка, находим ссылки, затем парсим детальные страницы по шаблону.</div>

          <div className="font-medium">Что заполнить</div>
          <ul className="list-disc pl-4">
            <li>
              <b>base_url</b> — URL раздела/ленты, например: <code>https://site.ru/news</code>
            </li>
            <li>
              <b>Шаблон парсинга</b> — JSON с CSS‑селекторами для детальной страницы
            </li>
          </ul>

          <div className="font-medium">Рекомендации</div>
          <ul className="list-disc pl-4">
            <li>Сначала создайте шаблон и прогоните “Тест шаблона” на одной статье.</li>
            <li>Начинайте с простых селекторов: <code>h1</code>, <code>time[datetime]</code>, <code>article</code>.</li>
          </ul>

          <div className="font-medium">Статус реализации</div>
          <div>
            “List→detail” ingestion подключён: мы находим ссылки на детальные статьи (по CSS-селектору) и парсим детали по шаблону.
          </div>
        </div>
      ) : null}

      {form.source_type === "HTML_DETAIL_ONLY" ? (
        <div className="space-y-2">
          <div className="font-medium">Для чего</div>
          <div>Когда у вас уже есть конкретные URL статей (или другой модуль будет их находить), и нужно только парсить “деталь”.</div>

          <div className="font-medium">Что заполнить</div>
          <ul className="list-disc pl-4">
            <li>
              <b>base_url</b> — любая детальная статья этого сайта (для первичной проверки), например:{" "}
              <code>https://site.ru/news/123</code>
            </li>
            <li>
              <b>Шаблон парсинга</b> — селекторы для title/date/author/body
            </li>
          </ul>

          <div className="font-medium">Как использовать правильно</div>
          <ul className="list-disc pl-4">
            <li>Проверьте шаблон на 2–3 разных статьях (старые/новые), чтобы селекторы были устойчивыми.</li>
            <li>Если body пустой — включайте fallback (у нас есть readability‑fallback в тесте).</li>
          </ul>

          <div className="font-medium">Статус реализации</div>
          <div>Ingestion “деталей” подключён: источник будет регулярно парсить указанный URL (полезно для проверки шаблона).</div>
        </div>
      ) : null}

      {isSitemap ? (
        <div className="space-y-2">
          <div className="font-medium">Для чего</div>
          <div>Для сайтов, где есть sitemap.xml и нужно автоматом находить новые URL статей.</div>

          <div className="font-medium">Что заполнить</div>
          <ul className="list-disc pl-4">
            <li>
              <b>base_url</b> — URL sitemap, например: <code>https://site.ru/sitemap.xml</code>
            </li>
            <li>
              (Рекомендуем) В <b>settings_json</b> добавьте фильтры URL, чтобы не тянуть лишнее:{" "}
              <code>{"{\"sitemap_include_regex\":\"/news/\",\"sitemap_exclude_regex\":\"/tag/\"}"}</code>
            </li>
          </ul>

          <div className="font-medium">Статус реализации</div>
          <div>Обход sitemap подключён: URLs берутся из sitemap, фильтруются regex-ами и парсятся как обычные HTML-детали (с шаблоном или readability fallback).</div>
        </div>
      ) : null}

      {isTelegram ? (
        <div className="space-y-2">
          <div className="font-medium">Для чего</div>
          <div>Публичные Telegram‑каналы конкурентов и медиа. Сбор через MTProto (Telethon).</div>

          <div className="font-medium">Что заполнить</div>
          <ul className="list-disc pl-4">
            <li>
              <b>Telegram канал</b> — username, например: <code>@somechannel</code>
            </li>
            <li>
              (Опционально) <b>Конкурент</b> — если это канал конкурента
            </li>
          </ul>

          <div className="font-medium">Как работает (план)</div>
          <ul className="list-disc pl-4">
            <li>Первичная выборка: последние N сообщений (по умолчанию 200).</li>
            <li>Инкрементально: забираем новые сообщения по last_message_id.</li>
            <li>“Хвост” пересматриваем, чтобы ловить правки/удаления.</li>
          </ul>

          <div className="font-medium">Важно</div>
          <ul className="list-disc pl-4">
            <li>Нужны TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_PHONE в окружении worker’а.</li>
            <li>FloodWait обрабатывается backoff’ом: источник ставится “на паузу” до указанного времени.</li>
          </ul>
        </div>
      ) : null}
    </InstructionBox>
  );

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Источники</h1>
          <p className="mt-1 text-sm text-slate-600">Единый реестр: сайты (HTML), RSS/Atom, Telegram-каналы. Добавление новых источников — через UI без изменения кода.</p>
          <HintBox>
            <div className="font-medium">Важно</div>
            <ul className="mt-1 list-disc pl-4">
              <li>Для <b>RSS_ATOM</b> нужен <code className="rounded bg-white px-1">feed_url</code>.</li>
              <li>Для <b>HTML_LIST_DETAIL / HTML_DETAIL_ONLY</b> нужен <code className="rounded bg-white px-1">base_url</code> и <code className="rounded bg-white px-1">parsing_template</code>.</li>
              <li>Для <b>TELEGRAM_CHANNEL</b> нужен <code className="rounded bg-white px-1">@username</code> (публичный).</li>
            </ul>
          </HintBox>
        </div>
        {canWrite ? (
          <button
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800"
            onClick={() => {
              setEditing(null);
              setForm(toForm());
              setModalOpen(true);
            }}
          >
            Добавить источник
          </button>
        ) : null}
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 overflow-x-auto rounded border bg-white">
        <table className="min-w-[1000px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Тип</th>
              <th className="px-3 py-2">Имя</th>
              <th className="px-3 py-2">URL</th>
              <th className="px-3 py-2">Enabled</th>
              <th className="px-3 py-2">Конкурент</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={6}>
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={6}>
                  Пусто
                </td>
              </tr>
            ) : (
              items.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-3 py-2">{s.source_type}</td>
                  <td className="px-3 py-2 font-medium">{s.name || "—"}</td>
                  <td className="px-3 py-2 text-xs text-slate-700">{s.base_url || s.feed_url || (s.tg_channel_username ? `@${s.tg_channel_username}` : "—")}</td>
                  <td className="px-3 py-2">{s.enabled ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">{s.competitor_id ? competitorById.get(s.competitor_id) || s.competitor_id : "—"}</td>
                  <td className="px-3 py-2 text-right">
                    {canWrite ? (
                      <div className="flex justify-end gap-2">
                        <button
                          className="rounded border px-2 py-1 text-xs hover:bg-slate-50"
                          onClick={() => {
                            setEditing(s);
                            setForm(toForm(s));
                            setModalOpen(true);
                          }}
                        >
                          Редактировать
                        </button>
                        <button
                          className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                          onClick={async () => {
                            if (!accessToken) return;
                            if (!confirm(`Удалить источник "${s.name || s.id}"?`)) return;
                            try {
                              await api.sources.delete(accessToken, s.id);
                              await reload();
                            } catch (e: any) {
                              push({ variant: "error", title: "Не удалось удалить", description: e?.message || "Ошибка удаления" });
                            }
                          }}
                        >
                          Удалить
                        </button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-lg bg-white shadow-lg">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-4 py-3">
              <div className="text-sm font-semibold">{editing ? "Редактировать источник" : "Новый источник"}</div>
              <button className="rounded px-2 py-1 text-sm hover:bg-slate-50" onClick={() => setModalOpen(false)}>
                ✕
              </button>
            </div>

            <div className="max-h-[calc(90vh-120px)] overflow-y-auto px-4 py-4">
              <div className="grid gap-3">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <label className="block">
                  <div className="text-sm text-slate-700">Тип источника</div>
                  <select
                    className="mt-1 w-full rounded border px-3 py-2 text-sm"
                    value={form.source_type}
                    onChange={(e) => {
                      const next = e.target.value;
                      setForm((f) => {
                        // Clear irrelevant fields to avoid confusion and backend validation errors.
                        const cleared: Partial<SourceForm> = {};
                        if (next === "RSS_ATOM") {
                          cleared.base_url = "";
                          cleared.tg_channel_username = "";
                          cleared.parsing_template_id = "";
                        } else if (next === "TELEGRAM_CHANNEL") {
                          cleared.base_url = "";
                          cleared.feed_url = "";
                          cleared.parsing_template_id = "";
                        } else if (next === "SITEMAP") {
                          cleared.feed_url = "";
                          cleared.tg_channel_username = "";
                          cleared.parsing_template_id = "";
                        } else {
                          // HTML_* types
                          cleared.feed_url = "";
                          cleared.tg_channel_username = "";
                        }
                        return { ...f, ...cleared, source_type: next };
                      });
                    }}
                  >
                    <option value="RSS_ATOM">RSS_ATOM</option>
                    <option value="HTML_LIST_DETAIL">HTML_LIST_DETAIL</option>
                    <option value="HTML_DETAIL_ONLY">HTML_DETAIL_ONLY</option>
                    <option value="SITEMAP">SITEMAP</option>
                    <option value="TELEGRAM_CHANNEL">TELEGRAM_CHANNEL</option>
                  </select>
                  <HelpText>Определяет стратегию загрузки (RSS, HTML-шаблон, Telegram).</HelpText>
                </label>
                <label className="block md:col-span-2">
                  <div className="text-sm text-slate-700">Имя (опционально)</div>
                  <input className="mt-1 w-full rounded border px-3 py-2 text-sm" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                  <HelpText>Для удобства в отчётах и мониторинге (например: “Конкурент X — новости”).</HelpText>
                </label>
              </div>

              <div className="rounded-lg border-2 border-amber-200 bg-amber-50 p-4">
                <div className="text-sm font-bold text-slate-800">Фильтр по словам</div>
                <p className="mt-1 text-xs text-slate-600">При сборе сохраняются только новости, прошедшие фильтр. Пусто = без фильтра.</p>
                <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Включить (хотя бы одно слово)</span>
                    <textarea
                      className="mt-1.5 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
                      rows={2}
                      placeholder="недвижимость, строительство, ипотека"
                      value={form.include_keywords}
                      onChange={(e) => setForm((f) => ({ ...f, include_keywords: e.target.value }))}
                    />
                    <span className="mt-1 block text-xs text-slate-500">Сохранять только если в заголовке/тексте есть хотя бы одно из слов.</span>
                  </label>
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Исключить</span>
                    <textarea
                      className="mt-1.5 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
                      rows={2}
                      placeholder="реклама, вакансия"
                      value={form.exclude_keywords}
                      onChange={(e) => setForm((f) => ({ ...f, exclude_keywords: e.target.value }))}
                    />
                    <span className="mt-1 block text-xs text-slate-500">Не сохранять, если в тексте есть любое из этих слов.</span>
                  </label>
                </div>
                {editing && isAdmin ? (
                  <div className="mt-3">
                    <button
                      type="button"
                      className="rounded border border-amber-300 bg-amber-100 px-3 py-1.5 text-sm text-amber-800 hover:bg-amber-200"
                      onClick={async () => {
                        if (!accessToken || !editing) return;
                        if (!confirm("Удалить из БД новости, не прошедшие текущий фильтр? Сначала сохраните источник с нужными ключами.")) return;
                        try {
                          const res = await api.sources.cleanupNews(accessToken, editing.id);
                          push({
                            variant: "success",
                            title: "Очистка выполнена",
                            description: `Удалено: ${res.deleted} из ${res.total_checked} проверенных`,
                          });
                          await reload();
                        } catch (e: any) {
                          push({ variant: "error", title: "Ошибка очистки", description: e?.message || "Ошибка" });
                        }
                      }}
                    >
                      Очистить старые новости по фильтру
                    </button>
                    <span className="ml-2 text-xs text-slate-500">Удаляет из БД записи, не соответствующие ключам выше.</span>
                  </div>
                ) : null}
              </div>

              {typeInstructions}

              {/* Type-specific required fields */}
              {isRss ? (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="block md:col-span-2">
                    <div className="text-sm text-slate-700">feed_url</div>
                    <input
                      className="mt-1 w-full rounded border px-3 py-2 text-sm"
                      value={form.feed_url}
                      onChange={(e) => setForm((f) => ({ ...f, feed_url: e.target.value }))}
                      placeholder="https://example.com/rss.xml"
                    />
                    <HelpText>URL RSS/Atom фида. Используется conditional GET (ETag/Last-Modified).</HelpText>
                  </label>
                </div>
              ) : null}

              {isHtml ? (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="block md:col-span-2">
                    <div className="text-sm text-slate-700">base_url</div>
                    <input
                      className="mt-1 w-full rounded border px-3 py-2 text-sm"
                      value={form.base_url}
                      onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                      placeholder={isSitemap ? "https://example.com/sitemap.xml" : "https://example.com/news"}
                    />
                    <HelpText>
                      {isSitemap
                        ? "URL sitemap.xml (пока только регистрация; обработку sitemap добавим следующим этапом)."
                        : "Стартовый URL для списка/раздела (или детальной страницы для DETAIL_ONLY)."}
                    </HelpText>
                  </label>
                </div>
              ) : null}

              {isTelegram ? (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="block md:col-span-2">
                    <div className="text-sm text-slate-700">Telegram канал</div>
                    <input
                      className="mt-1 w-full rounded border px-3 py-2 text-sm"
                      value={form.tg_channel_username}
                      onChange={(e) => setForm((f) => ({ ...f, tg_channel_username: e.target.value }))}
                      placeholder="@channelname"
                    />
                    <HelpText>Публичный канал. Можно вводить с @ или без. Пример ссылки новости будет вида: https://t.me/&lt;username&gt;/&lt;id&gt;</HelpText>
                  </label>
                </div>
              ) : null}

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <label className="block">
                  <div className="text-sm text-slate-700">Конкурент (опционально)</div>
                  <select className="mt-1 w-full rounded border px-3 py-2 text-sm" value={form.competitor_id} onChange={(e) => setForm((f) => ({ ...f, competitor_id: e.target.value }))}>
                    <option value="">—</option>
                    {competitors.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  <HelpText>Если задано — источник попадёт в конкурентный раздел отчёта.</HelpText>
                </label>
                {needsTemplate ? (
                  <label className="block">
                    <div className="text-sm text-slate-700">Шаблон парсинга</div>
                    <select
                      className="mt-1 w-full rounded border px-3 py-2 text-sm"
                      value={form.parsing_template_id}
                      onChange={(e) => setForm((f) => ({ ...f, parsing_template_id: e.target.value }))}
                    >
                      <option value="">—</option>
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name} v{t.version}
                        </option>
                      ))}
                    </select>
                    <HelpText>Обязателен для HTML_LIST_DETAIL / HTML_DETAIL_ONLY.</HelpText>
                  </label>
                ) : (
                  <div className="rounded border bg-slate-50 p-3 text-xs text-slate-700">
                    Для выбранного типа шаблон парсинга не требуется.
                  </div>
                )}
              </div>

              <div>
                <div className="text-sm text-slate-700">Регионы источника</div>
                <HelpText>Источники можно заранее размечать регионами/дивизионами (влияет на маршрутизацию и выборку в отчёте).</HelpText>
                <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                  {regions.map((r) => (
                    <label key={r.id} className="inline-flex items-center gap-2 rounded border bg-white px-2 py-1 text-sm">
                      <input
                        type="checkbox"
                        checked={form.region_tags.includes(r.id)}
                        onChange={(e) => {
                          setForm((f) => {
                            const set = new Set(f.region_tags);
                            if (e.target.checked) set.add(r.id);
                            else set.delete(r.id);
                            return { ...f, region_tags: Array.from(set) };
                          });
                        }}
                      />
                      <span>{r.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Collapsible-ish "Advanced" (simple) */}
              <div className="mt-2 rounded border bg-white">
                <details>
                  <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-slate-800">
                    Дополнительно (частота, лимиты, retries, robots.txt, settings)
                  </summary>
                  <div className="grid gap-3 px-3 pb-3">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                      <label className="block">
                        <div className="text-sm text-slate-700">Частота (мин)</div>
                        <input
                          className="mt-1 w-full rounded border px-3 py-2 text-sm"
                          type="number"
                          value={form.fetch_frequency_min}
                          onChange={(e) => setForm((f) => ({ ...f, fetch_frequency_min: Number(e.target.value || 60) }))}
                        />
                        <HelpText>Как часто планировщик будет ставить задачи на загрузку источника.</HelpText>
                      </label>
                      <label className="block">
                        <div className="text-sm text-slate-700">Приоритет</div>
                        <input
                          className="mt-1 w-full rounded border px-3 py-2 text-sm"
                          type="number"
                          value={form.priority}
                          onChange={(e) => setForm((f) => ({ ...f, priority: Number(e.target.value || 0) }))}
                        />
                        <HelpText>Выше = раньше в очереди.</HelpText>
                      </label>
                      <label className="block">
                        <div className="text-sm text-slate-700">Задержка (ms)</div>
                        <input
                          className="mt-1 w-full rounded border px-3 py-2 text-sm"
                          type="number"
                          value={form.delay_ms}
                          onChange={(e) => setForm((f) => ({ ...f, delay_ms: Number(e.target.value || 0) }))}
                        />
                        <HelpText>Пауза между запросами (политика вежливости).</HelpText>
                      </label>
                    </div>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                      <label className="block">
                        <div className="text-sm text-slate-700">Лимит rpm</div>
                        <input
                          className="mt-1 w-full rounded border px-3 py-2 text-sm"
                          type="number"
                          value={form.max_requests_per_minute}
                          onChange={(e) => setForm((f) => ({ ...f, max_requests_per_minute: Number(e.target.value || 60) }))}
                        />
                        <HelpText>Максимум запросов/мин для источника (для будущих throttling-лимитов).</HelpText>
                      </label>
                      <label className="block">
                        <div className="text-sm text-slate-700">Retries</div>
                        <input
                          className="mt-1 w-full rounded border px-3 py-2 text-sm"
                          type="number"
                          value={form.retries}
                          onChange={(e) => setForm((f) => ({ ...f, retries: Number(e.target.value || 3) }))}
                        />
                        <HelpText>Сколько раз RQ будет повторять задачу при падении.</HelpText>
                      </label>
                      <label className="inline-flex items-center gap-2 pt-6">
                        <input type="checkbox" checked={form.enabled} onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))} />
                        <span className="text-sm text-slate-700">Enabled</span>
                        <span className="text-xs text-slate-500">Отключённые источники не планируются.</span>
                      </label>
                    </div>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <label className="inline-flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={form.respect_robots_txt}
                          onChange={(e) => setForm((f) => ({ ...f, respect_robots_txt: e.target.checked }))}
                        />
                        <span className="text-sm text-slate-700">Respect robots.txt</span>
                        <span className="text-xs text-slate-500">По умолчанию выключено (включайте при необходимости).</span>
                      </label>
                    </div>

                    <label className="block">
                      <div className="text-sm text-slate-700">settings_json (доп. настройки)</div>
                      <textarea
                        className="mt-1 h-44 w-full rounded border px-3 py-2 font-mono text-xs"
                        value={form.settings_json_text}
                        onChange={(e) => setForm((f) => ({ ...f, settings_json_text: e.target.value }))}
                      />
                      <HelpText>JSON для специальных опций (RSS/TG/HTML). Позже добавим валидатор по типу источника.</HelpText>
                    </label>
                  </div>
                </details>
              </div>
            </div>
            </div>

            <div className="sticky bottom-0 z-10 flex items-center justify-end gap-2 border-t bg-white px-4 py-3">
              <button className="rounded border px-3 py-2 text-sm hover:bg-slate-50" onClick={() => setModalOpen(false)}>
                Отмена
              </button>
              <button
                className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800"
                onClick={async () => {
                  if (!accessToken) return;
                  try {
                    const settings_json = JSON.parse(form.settings_json_text || "{}");
                    const payload: any = {
                      source_type: form.source_type,
                      name: form.name || null,
                      base_url: form.base_url || null,
                      feed_url: form.feed_url || null,
                      tg_channel_username: form.tg_channel_username || null,
                      competitor_id: form.competitor_id || null,
                      region_tags: form.region_tags,
                      enabled: form.enabled,
                      fetch_frequency_min: form.fetch_frequency_min,
                      priority: form.priority,
                      delay_ms: form.delay_ms,
                      max_requests_per_minute: form.max_requests_per_minute,
                      retries: form.retries,
                      respect_robots_txt: form.respect_robots_txt,
                      parsing_template_id: form.parsing_template_id || null,
                      settings_json: {
                        ...settings_json,
                        include_keywords: parseKeywords(form.include_keywords),
                        exclude_keywords: parseKeywords(form.exclude_keywords),
                      },
                    };
                    if (editing) await api.sources.update(accessToken, editing.id, payload);
                    else await api.sources.create(accessToken, payload);
                    setModalOpen(false);
                    await reload();
                  } catch (e: any) {
                    push({
                      variant: "error",
                      title: "Не удалось сохранить",
                      description: e?.message || "Ошибка сохранения (проверьте обязательные поля и JSON)",
                    });
                  }
                }}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

