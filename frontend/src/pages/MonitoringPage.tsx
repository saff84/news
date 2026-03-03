import { useEffect, useState } from "react";
import { api, type SourceHealthOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { HintBox } from "../components/Field";

export function MonitoringPage() {
  const { accessToken } = useAuth();
  const [onlyFailed, setOnlyFailed] = useState(true);
  const [items, setItems] = useState<SourceHealthOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.monitoring.sources(accessToken, onlyFailed);
      setItems(res.items);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyFailed]);

  return (
    <div>
      <h1 className="text-lg font-semibold">Мониторинг</h1>
      <p className="mt-1 text-sm text-slate-600">Состояние источников: ошибки, количество подряд неудачных запусков, backoff.</p>
      <HintBox>
        <div className="font-medium">Как читать</div>
        <ul className="mt-1 list-disc pl-4">
          <li><b>last_error</b> — последняя ошибка парсинга/загрузки</li>
          <li><b>consecutive_failures</b> — сколько раз подряд источник упал</li>
          <li><b>backoff_until</b> — до какого времени источник “на паузе” (после ошибок/лимитов)</li>
        </ul>
      </HintBox>

      <div className="mt-4 flex items-center justify-between gap-2">
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyFailed} onChange={(e) => setOnlyFailed(e.target.checked)} />
          Только проблемные
        </label>
        <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" onClick={reload} disabled={loading}>
          Обновить
        </button>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 overflow-x-auto rounded border bg-white">
        <table className="min-w-[900px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Тип</th>
              <th className="px-3 py-2">Имя/URL</th>
              <th className="px-3 py-2">Enabled</th>
              <th className="px-3 py-2">Fail</th>
              <th className="px-3 py-2">Last success</th>
              <th className="px-3 py-2">Last error</th>
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
                  Нет данных
                </td>
              </tr>
            ) : (
              items.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-3 py-2">{s.source_type}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{s.name || "—"}</div>
                    <div className="text-xs text-slate-600">{s.base_url || s.feed_url || (s.tg_channel_username ? `@${s.tg_channel_username}` : "")}</div>
                  </td>
                  <td className="px-3 py-2">{s.enabled ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">{s.consecutive_failures}</td>
                  <td className="px-3 py-2 text-xs text-slate-700">{s.last_success_at || "—"}</td>
                  <td className="px-3 py-2 text-xs text-red-700">{s.last_error || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

