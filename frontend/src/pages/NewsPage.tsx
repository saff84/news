import { useEffect, useState } from "react";
import { ExternalLink, Trash2 } from "lucide-react";
import { api, type NewsItemOut, type SourceOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

function formatDate(s: string | null): string {
  if (!s) return "—";
  try {
    const d = new Date(s);
    return d.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return s;
  }
}

function truncate(s: string | null, maxLen: number): string {
  if (!s) return "—";
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen) + "…";
}

export function NewsPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";
  const [items, setItems] = useState<NewsItemOut[]>([]);
  const [sources, setSources] = useState<SourceOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [sourceId, setSourceId] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 30;

  const reload = async (overrides?: { offset?: number }) => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    const off = overrides?.offset ?? offset;
    try {
      const [newsRes, sourcesRes] = await Promise.all([
        api.news.list(accessToken, { q: q || undefined, source_id: sourceId || undefined, offset: off, limit }),
        api.sources.list(accessToken),
      ]);
      setItems(newsRes.items);
      setTotal(newsRes.total);
      setSources(sourcesRes.items);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, sourceId]);

  const handleSearch = () => {
    setOffset(0);
    reload({ offset: 0 });
  };

  const handleDelete = async (n: NewsItemOut) => {
    if (!accessToken || !isAdmin) return;
    if (!confirm(`Удалить новость "${(n.title || "").slice(0, 50)}…"?`)) return;
    try {
      await api.news.delete(accessToken, n.id);
      push({ variant: "success", title: "Удалено", description: "Новость удалена" });
      await reload();
    } catch (e: any) {
      push({ variant: "error", title: "Не удалось удалить", description: e?.message || "Ошибка" });
    }
  };

  return (
    <div>
      <h1 className="text-lg font-semibold">Новости</h1>
      <p className="mt-1 text-sm text-slate-600">
        Собранные новости из источников. Всего: {total}
      </p>
      <HintBox>
        <div className="font-medium">Как читать</div>
        <ul className="mt-1 list-disc pl-4">
          <li><b>Источник</b> — откуда загружена новость</li>
          <li><b>Дата</b> — published_at или дата добавления</li>
          <li><b>Сниппет</b> — краткое превью текста</li>
        </ul>
      </HintBox>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          className="rounded border bg-white px-3 py-2 text-sm"
          placeholder="Поиск по заголовку/сниппету…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <select
          className="rounded border bg-white px-3 py-2 text-sm"
          value={sourceId}
          onChange={(e) => {
            setSourceId(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все источники</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name || s.base_url || s.feed_url || (s.tg_channel_username ? `@${s.tg_channel_username}` : s.id)}
            </option>
          ))}
        </select>
        <button
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800"
          onClick={handleSearch}
          disabled={loading}
        >
          Поиск
        </button>
        <button
          className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50"
          onClick={reload}
          disabled={loading}
        >
          Обновить
        </button>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 overflow-x-auto rounded border bg-white">
        <table className="min-w-[900px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Заголовок</th>
              <th className="px-3 py-2">Источник</th>
              <th className="px-3 py-2">Дата</th>
              <th className="px-3 py-2">Сниппет</th>
              <th className="px-3 py-2 w-24">Действия</th>
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
                  Нет данных. Добавьте источники и дождитесь сбора.
                </td>
              </tr>
            ) : (
              items.map((n) => (
                <tr key={n.id} className="border-t">
                  <td className="max-w-[400px] px-3 py-2">
                    <div className="font-medium whitespace-normal break-words">
                      {n.title || "—"}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600 max-w-[180px] truncate" title={n.source_name || undefined}>
                    {n.source_name || "—"}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-700 whitespace-nowrap">
                    {formatDate(n.published_at || n.created_at)}
                  </td>
                  <td className="max-w-[300px] px-3 py-2 text-xs text-slate-600 whitespace-normal break-words">
                    {truncate(n.snippet || n.content_text, 200)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      <a
                        href={n.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex text-slate-600 hover:text-slate-900"
                        aria-label="Открыть ссылку"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                      {isAdmin ? (
                        <button
                          type="button"
                          onClick={() => handleDelete(n)}
                          className="inline-flex text-red-600 hover:text-red-800"
                          aria-label="Удалить"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > limit && (
        <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
          <span>
            Показано {offset + 1}–{Math.min(offset + limit, total)} из {total}
          </span>
          <div className="flex gap-2">
            <button
              className="rounded border bg-white px-3 py-1.5 hover:bg-slate-50 disabled:opacity-50"
              disabled={offset === 0 || loading}
              onClick={() => setOffset((o) => Math.max(0, o - limit))}
            >
              Назад
            </button>
            <button
              className="rounded border bg-white px-3 py-1.5 hover:bg-slate-50 disabled:opacity-50"
              disabled={offset + limit >= total || loading}
              onClick={() => setOffset((o) => o + limit)}
            >
              Далее
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
