import { useEffect, useState } from "react";
import { api, type MonitoringAlertOut, type SourceHealthOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { HintBox } from "../components/Field";

export function MonitoringPage() {
  const { accessToken } = useAuth();
  const [onlyFailed, setOnlyFailed] = useState(true);
  const [items, setItems] = useState<SourceHealthOut[]>([]);
  const [alerts, setAlerts] = useState<MonitoringAlertOut[]>([]);
  const [criticalCount, setCriticalCount] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [res, alertRes] = await Promise.all([
        api.monitoring.sources(accessToken, onlyFailed),
        api.monitoring.alerts(accessToken, { limit: 100 }),
      ]);
      setItems(res.items);
      setAlerts(alertRes.items);
      setCriticalCount(alertRes.critical_count);
      setWarningCount(alertRes.warning_count);
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

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Critical alerts</div>
          <div className="mt-1 text-lg font-semibold text-red-700">{criticalCount}</div>
        </div>
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Warning alerts</div>
          <div className="mt-1 text-lg font-semibold text-amber-700">{warningCount}</div>
        </div>
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Всего источников в списке</div>
          <div className="mt-1 text-lg font-semibold">{items.length}</div>
        </div>
      </div>

      <div className="mt-4 rounded border bg-white">
        <div className="border-b px-3 py-2 text-sm font-semibold">Активные алерты</div>
        <div className="max-h-64 overflow-auto">
          {loading ? (
            <div className="px-3 py-3 text-sm text-slate-600">Загрузка…</div>
          ) : alerts.length === 0 ? (
            <div className="px-3 py-3 text-sm text-emerald-700">Алертов нет.</div>
          ) : (
            <ul className="divide-y">
              {alerts.map((a) => (
                <li key={a.id} className="px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        a.severity === "critical"
                          ? "bg-red-100 text-red-800"
                          : a.severity === "warning"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {a.severity}
                    </span>
                    <span className="text-xs text-slate-500">{a.code}</span>
                  </div>
                  <div className="mt-1">{a.message}</div>
                  {a.source_label ? <div className="text-xs text-slate-500">{a.source_label}</div> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

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

