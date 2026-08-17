import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, ExternalLink, Play, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import {
  api,
  type CompetitorOut,
  type CompetitorTelegramPostOut,
  type CompetitorTelegramProfileOut,
  type CompetitorTelegramSummaryOut,
} from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

type ProfileForm = {
  competitor_id: string;
  tg_channel_username: string;
  include_keywords: string;
  exclude_keywords: string;
  match_whole_words: boolean;
  backfill_until_date: string;
  is_active: boolean;
};

function parseKeywords(s: string): string[] {
  return s
    .split(/[\n,;]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function defaultUntilDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 24);
  return d.toISOString().slice(0, 10);
}

function formatDateTime(s: string | null | undefined) {
  if (!s) return "—";
  try {
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(s));
  } catch {
    return s;
  }
}

function formatTelegramError(raw: string | null | undefined): string | null {
  if (!raw?.trim()) return null;
  const low = raw.toLowerCase();
  if (low.includes("connection to telegram failed")) {
    return "Не удалось подключиться к Telegram. Проверьте интернет/VPN и авторизацию в разделе «Telegram-парсер».";
  }
  if (low.includes("credentials not configured") || low.includes("telegram credentials")) {
    return "Telegram-парсер не настроен. Укажите api_id, api_hash и выполните вход по QR.";
  }
  if (low.includes("not authorized") || low.includes("session is not authorized")) {
    return "Сессия Telegram не авторизована. Выполните вход в разделе «Telegram-парсер».";
  }
  return raw;
}

function statusLabel(p: CompetitorTelegramProfileOut, tgReady: boolean) {
  if (p.last_error) {
    const isTg = /telegram|credentials|authorized|connection to telegram/i.test(p.last_error);
    return { text: isTg ? "TG не подключён" : "Ошибка сбора", cls: "bg-red-50 text-red-700" };
  }
  if (!tgReady && p.posts_count === 0) return { text: "TG не настроен", cls: "bg-amber-50 text-amber-800" };
  if (!p.backfill_complete) return { text: "Сбор истории…", cls: "bg-amber-50 text-amber-800" };
  if (p.summary_status === "approved") return { text: "Одобрено", cls: "bg-emerald-50 text-emerald-700" };
  if (p.summary_status === "ready") return { text: "Саммари готово", cls: "bg-blue-50 text-blue-700" };
  if (p.posts_count > 0) return { text: "Посты собраны", cls: "bg-slate-100 text-slate-700" };
  return { text: "Нет данных", cls: "bg-slate-100 text-slate-600" };
}

export function CompetitorTelegramPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";

  const [profiles, setProfiles] = useState<CompetitorTelegramProfileOut[]>([]);
  const [competitors, setCompetitors] = useState<CompetitorOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<ProfileForm>(() => ({
    competitor_id: "",
    tg_channel_username: "",
    include_keywords: "",
    exclude_keywords: "",
    match_whole_words: false,
    backfill_until_date: defaultUntilDate(),
    is_active: true,
  }));

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [posts, setPosts] = useState<CompetitorTelegramPostOut[]>([]);
  const [postsTotal, setPostsTotal] = useState(0);
  const [summary, setSummary] = useState<CompetitorTelegramSummaryOut | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [tgStatus, setTgStatus] = useState<{
    ready: boolean;
    message: string | null;
    credentials_configured: boolean;
    session_configured: boolean;
  } | null>(null);

  const selected = useMemo(() => profiles.find((p) => p.id === selectedId) ?? null, [profiles, selectedId]);

  const usedCompetitorIds = useMemo(() => new Set(profiles.map((p) => p.competitor_id)), [profiles]);
  const availableCompetitors = useMemo(
    () => competitors.filter((c) => c.is_active && !usedCompetitorIds.has(c.id)),
    [competitors, usedCompetitorIds],
  );

  const reloadProfiles = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [p, c, tg] = await Promise.all([
        api.competitorTelegram.listProfiles(accessToken),
        api.competitors.list(accessToken),
        api.competitorTelegram.telegramStatus(accessToken),
      ]);
      setProfiles(p.items);
      setCompetitors(c.items);
      setTgStatus(tg);
      if (!selectedId && p.items.length) setSelectedId(p.items[0].id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [accessToken, selectedId]);

  const reloadDetail = useCallback(async () => {
    if (!accessToken || !selectedId) {
      setPosts([]);
      setPostsTotal(0);
      setSummary(null);
      return;
    }
    try {
      const [postsRes, summaryRes] = await Promise.all([
        api.competitorTelegram.listPosts(accessToken, selectedId, { limit: 30 }),
        api.competitorTelegram.getSummary(accessToken, selectedId),
      ]);
      setPosts(postsRes.items);
      setPostsTotal(postsRes.total);
      setSummary(summaryRes);
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Ошибка загрузки деталей" });
    }
  }, [accessToken, selectedId, push]);

  useEffect(() => {
    reloadProfiles();
  }, [reloadProfiles]);

  useEffect(() => {
    reloadDetail();
  }, [reloadDetail]);

  const createProfile = async () => {
    if (!accessToken || !form.competitor_id || !form.tg_channel_username.trim()) return;
    setBusy("create");
    try {
      const created = await api.competitorTelegram.createProfile(accessToken, {
        competitor_id: form.competitor_id,
        tg_channel_username: form.tg_channel_username.trim().replace(/^@/, ""),
        include_keywords: parseKeywords(form.include_keywords),
        exclude_keywords: parseKeywords(form.exclude_keywords),
        match_whole_words: form.match_whole_words,
        backfill_until_date: form.backfill_until_date || null,
        is_active: form.is_active,
      });
      push({ variant: "success", title: "TG-анализ", description: "Профиль добавлен" });
      setModalOpen(false);
      setSelectedId(created.id);
      await reloadProfiles();
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Не удалось создать" });
    } finally {
      setBusy(null);
    }
  };

  const runCollect = async (reset = false) => {
    if (!accessToken || !selectedId) return;
    setBusy("collect");
    try {
      const res = await api.competitorTelegram.collect(accessToken, selectedId, { reset_history: reset });
      push({
        variant: "success",
        title: "TG-анализ",
        description:
          res.status === "queued"
            ? "Сбор поставлен в очередь. История до 24 мес. подтягивается батчами."
            : `Добавлено постов: ${res.inserted ?? 0}. Всего: ${res.total_posts ?? "?"}`,
      });
      await reloadProfiles();
      await reloadDetail();
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Ошибка сбора" });
    } finally {
      setBusy(null);
    }
  };

  const runSummarize = async () => {
    if (!accessToken || !selectedId) return;
    setBusy("summarize");
    try {
      const s = await api.competitorTelegram.summarize(accessToken, selectedId);
      setSummary(s);
      push({ variant: "success", title: "TG-анализ", description: "Саммари сгенерировано" });
      await reloadProfiles();
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Ошибка ИИ" });
    } finally {
      setBusy(null);
    }
  };

  const approve = async () => {
    if (!accessToken || !selectedId) return;
    setBusy("approve");
    try {
      await api.competitorTelegram.approveSummary(accessToken, selectedId);
      push({ variant: "success", title: "TG-анализ", description: "Саммари одобрено" });
      await reloadProfiles();
      await reloadDetail();
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Ошибка" });
    } finally {
      setBusy(null);
    }
  };

  const purge = async () => {
    if (!accessToken || !selectedId) return;
    if (!window.confirm("Удалить все спарсенные посты? Саммари и HTML-страница сохранятся.")) return;
    setBusy("purge");
    try {
      const res = await api.competitorTelegram.purgePosts(accessToken, selectedId);
      push({ variant: "success", title: "TG-анализ", description: `Удалено постов: ${res.deleted_posts}` });
      await reloadProfiles();
      await reloadDetail();
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Ошибка очистки" });
    } finally {
      setBusy(null);
    }
  };

  const deleteProfile = async (id: string) => {
    if (!accessToken || !window.confirm("Удалить профиль и все данные?")) return;
    setBusy("delete");
    try {
      await api.competitorTelegram.deleteProfile(accessToken, id);
      if (selectedId === id) setSelectedId(null);
      await reloadProfiles();
    } catch (e: unknown) {
      push({ variant: "error", title: "TG-анализ", description: e instanceof Error ? e.message : "Ошибка удаления" });
    } finally {
      setBusy(null);
    }
  };

  const summaryUrl = selected?.summary_html_path || summary?.html_path;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">TG-анализ конкурентов</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Отдельный парсинг Telegram-каналов конкурентов за период до 24 месяцев, AI-саммари по каждому и публикация HTML-страницы.
            После проверки можно удалить сырые посты, чтобы не занимать место в БД.
          </p>
          <HintBox>
            <div className="font-medium">Порядок работы</div>
            <ol className="mt-1 list-decimal space-y-1 pl-4 text-sm">
              <li>Добавьте конкурента и укажите @канал Telegram.</li>
              <li>Запустите сбор — история подтягивается батчами через worker (до даты «с …»).</li>
              <li>Сгенерируйте саммари (промпт «TG-архив конкурентов» в разделе ИИ).</li>
              <li>Откройте HTML-страницу, проверьте, одобрите и удалите посты.</li>
            </ol>
          </HintBox>
        </div>
        {isAdmin ? (
          <button
            className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800"
            onClick={() => {
              setForm({
                competitor_id: availableCompetitors[0]?.id ?? "",
                tg_channel_username: "",
                include_keywords: "",
                exclude_keywords: "",
                match_whole_words: false,
                backfill_until_date: defaultUntilDate(),
                is_active: true,
              });
              setModalOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            Добавить канал
          </button>
        ) : null}
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      {tgStatus && !tgStatus.ready ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <div className="font-semibold">Telegram-парсер не готов к сбору</div>
          <p className="mt-1">{tgStatus.message || "Настройте подключение к Telegram перед сбором постов."}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-amber-900">
            <li>api_id / api_hash: {tgStatus.credentials_configured ? "заданы" : "не заданы"}</li>
            <li>Сессия (QR или session string): {tgStatus.session_configured ? "есть" : "нет"}</li>
          </ul>
          <Link
            to="/telegram-parser"
            className="mt-3 inline-flex rounded border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-950 hover:bg-amber-100"
          >
            Открыть «Telegram-парсер» →
          </Link>
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
        <div className="overflow-hidden rounded border bg-white">
          <div className="border-b bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">Конкуренты для парсинга</div>
          {loading ? (
            <div className="p-4 text-sm text-slate-600">Загрузка…</div>
          ) : profiles.length === 0 ? (
            <div className="p-4 text-sm text-slate-600">Пока нет профилей. Добавьте канал конкурента.</div>
          ) : (
            <ul className="divide-y">
              {profiles.map((p) => {
                const st = statusLabel(p, tgStatus?.ready ?? true);
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      className={`w-full px-3 py-3 text-left text-sm hover:bg-slate-50 ${selectedId === p.id ? "bg-slate-100" : ""}`}
                      onClick={() => setSelectedId(p.id)}
                    >
                      <div className="font-medium">{p.competitor_name}</div>
                      <div className="text-slate-600">@{p.tg_channel_username}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <span className={`rounded px-2 py-0.5 text-xs ${st.cls}`}>{st.text}</span>
                        <span className="text-xs text-slate-500">{p.posts_count} постов</span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="min-w-0 space-y-4">
          {!selected ? (
            <div className="rounded border bg-white p-6 text-sm text-slate-600">Выберите профиль слева.</div>
          ) : (
            <>
              <div className="rounded border bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">{selected.competitor_name}</h2>
                    <p className="text-sm text-slate-600">
                      @{selected.tg_channel_username} · с {selected.backfill_until_date ?? defaultUntilDate()} · постов: {selected.posts_count}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Последний сбор: {formatDateTime(selected.last_fetch_at)}</p>
                    {selected.last_error ? (
                      <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                        <div className="font-medium">Ошибка последнего сбора</div>
                        <p className="mt-1">{formatTelegramError(selected.last_error) || selected.last_error}</p>
                        {/telegram|credentials|authorized|connection to telegram/i.test(selected.last_error) ? (
                          <Link to="/telegram-parser" className="mt-2 inline-block text-red-900 underline hover:no-underline">
                            Настроить Telegram-парсер
                          </Link>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                  {isAdmin ? (
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="inline-flex items-center gap-1 rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                        disabled={!!busy || tgStatus?.ready === false}
                        title={tgStatus?.ready === false ? tgStatus.message || "Сначала настройте Telegram-парсер" : undefined}
                        onClick={() => runCollect(false)}
                      >
                        <Play className="h-3.5 w-3.5" />
                        {busy === "collect" ? "Запуск…" : "Собрать"}
                      </button>
                      <button
                        className="rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                        disabled={!!busy || tgStatus?.ready === false}
                        onClick={() => runCollect(true)}
                      >
                        Сброс + история
                      </button>
                      <button
                        className="inline-flex items-center gap-1 rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                        disabled={!!busy || selected.posts_count === 0}
                        onClick={runSummarize}
                      >
                        <Bot className="h-3.5 w-3.5" />
                        {busy === "summarize" ? "ИИ…" : "Саммари ИИ"}
                      </button>
                      {summaryUrl ? (
                        <a
                          className="inline-flex items-center gap-1 rounded border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-800 hover:bg-blue-100"
                          href={summaryUrl}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                          Страница
                        </a>
                      ) : null}
                      {selected.summary_status === "ready" ? (
                        <button
                          className="rounded border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
                          disabled={!!busy}
                          onClick={approve}
                        >
                          Одобрить
                        </button>
                      ) : null}
                      {selected.summary_status === "approved" && selected.posts_count > 0 ? (
                        <button
                          className="inline-flex items-center gap-1 rounded border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-800 hover:bg-red-100 disabled:opacity-50"
                          disabled={!!busy}
                          onClick={purge}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Удалить посты
                        </button>
                      ) : null}
                      <button
                        className="rounded border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                        disabled={!!busy}
                        onClick={() => deleteProfile(selected.id)}
                      >
                        Удалить профиль
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>

              {summary?.summary_text ? (
                <div className="rounded border bg-white p-4">
                  <h3 className="text-sm font-semibold text-slate-800">Превью саммари</h3>
                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{summary.summary_text.slice(0, 3000)}</pre>
                </div>
              ) : null}

              <div className="overflow-x-auto rounded border bg-white">
                <div className="border-b bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
                  Посты ({postsTotal})
                </div>
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-700">
                    <tr>
                      <th className="px-3 py-2">Дата</th>
                      <th className="px-3 py-2">Текст</th>
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {posts.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-3 py-4 text-slate-600">
                          Нет постов. Запустите сбор.
                        </td>
                      </tr>
                    ) : (
                      posts.map((post) => (
                        <tr key={post.id} className="border-t align-top">
                          <td className="whitespace-nowrap px-3 py-2 text-slate-600">{formatDateTime(post.published_at)}</td>
                          <td className="max-w-xl px-3 py-2">{(post.text || "").slice(0, 240)}{(post.text || "").length > 240 ? "…" : ""}</td>
                          <td className="px-3 py-2">
                            <a className="text-blue-600 hover:underline" href={post.post_url} target="_blank" rel="noreferrer">
                              TG
                            </a>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      {modalOpen && isAdmin ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-5 shadow-xl">
            <h2 className="text-base font-semibold">Канал конкурента</h2>
            <div className="mt-4 grid gap-3">
              <label className="grid gap-1 text-sm">
                <span>Конкурент</span>
                <select
                  className="rounded border px-3 py-2"
                  value={form.competitor_id}
                  onChange={(e) => setForm((f) => ({ ...f, competitor_id: e.target.value }))}
                >
                  <option value="">— выберите —</option>
                  {availableCompetitors.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm">
                <span>Telegram @канал</span>
                <input
                  className="rounded border px-3 py-2"
                  placeholder="channel_username"
                  value={form.tg_channel_username}
                  onChange={(e) => setForm((f) => ({ ...f, tg_channel_username: e.target.value }))}
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span>Собирать посты с даты (24 мес. по умолчанию)</span>
                <input
                  type="date"
                  className="rounded border px-3 py-2"
                  value={form.backfill_until_date}
                  onChange={(e) => setForm((f) => ({ ...f, backfill_until_date: e.target.value }))}
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span>Include-ключи (по строке, пусто = все посты)</span>
                <textarea className="min-h-[72px] rounded border px-3 py-2 font-mono text-xs" value={form.include_keywords} onChange={(e) => setForm((f) => ({ ...f, include_keywords: e.target.value }))} />
              </label>
              <label className="grid gap-1 text-sm">
                <span>Exclude-ключи</span>
                <textarea className="min-h-[72px] rounded border px-3 py-2 font-mono text-xs" value={form.exclude_keywords} onChange={(e) => setForm((f) => ({ ...f, exclude_keywords: e.target.value }))} />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.match_whole_words} onChange={(e) => setForm((f) => ({ ...f, match_whole_words: e.target.checked }))} />
                Целые слова
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button className="rounded border px-3 py-2 text-sm hover:bg-slate-50" onClick={() => setModalOpen(false)}>
                Отмена
              </button>
              <button
                className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
                disabled={busy === "create" || !form.competitor_id || !form.tg_channel_username.trim()}
                onClick={createProfile}
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
