import { useEffect, useMemo, useState } from "react";
import { api, type MonitoringAlertOut, type SourceOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { HintBox } from "../components/Field";

type Overview = {
  now: string;
  db_ok: boolean;
  redis_ok: boolean;
  rq_default_queue_count: number;
  alembic_version?: string | null;
  alert_critical_count: number;
  alert_warning_count: number;
};

export function DiagnosticsPage() {
  const { accessToken, user } = useAuth();
  const isAdmin = user?.role === "Admin";

  const [overview, setOverview] = useState<Overview | null>(null);
  const [sources, setSources] = useState<SourceOut[]>([]);
  const [alerts, setAlerts] = useState<MonitoringAlertOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [runSourceId, setRunSourceId] = useState<string>("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any>(null);
  const [jobError, setJobError] = useState<string | null>(null);

  const [clusterJobId, setClusterJobId] = useState<string | null>(null);
  const [clusterJobStatus, setClusterJobStatus] = useState<any>(null);
  const [clusterJobError, setClusterJobError] = useState<string | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [ov, src] = await Promise.all([
        api.diagnostics.overview(accessToken),
        api.sources.list(accessToken),
      ]);
      setOverview(ov);
      setSources(src.items);
      const alertRes = await api.monitoring.alerts(accessToken, { limit: 20 });
      setAlerts(alertRes.items);
      if (!runSourceId && src.items[0]) setRunSourceId(src.items[0].id);
    } catch (e: any) {
      setError(e?.message || "Ошибка диагностики");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const statusBadge = (ok: boolean) => (
    <span className={`rounded px-2 py-0.5 text-xs ${ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
      {ok ? "OK" : "FAIL"}
    </span>
  );

  const sourceLabel = useMemo(() => new Map(sources.map((s) => [s.id, `${s.source_type} — ${s.name || s.base_url || s.feed_url || (s.tg_channel_username ? `@${s.tg_channel_username}` : s.id)}`])), [sources]);

  return (
    <div>
      <h1 className="text-lg font-semibold">Диагностика</h1>
      <p className="mt-1 text-sm text-slate-600">Быстрая проверка инфраструктуры и конфигурации, плюс “прогон” источника в очередь.</p>

      <HintBox>
        <div className="font-medium">Что можно проверить прямо сейчас</div>
        <ul className="mt-1 list-disc pl-4">
          <li>доступность PostgreSQL и Redis</li>
          <li>применены ли миграции (alembic_version)</li>
          <li>очередь RQ (сколько задач ожидает)</li>
          <li>enqueue задачи “запустить источник сейчас” и посмотреть статус job</li>
          <li>enqueue пересборки кластеров похожих новостей (simhash) для отчётов</li>
        </ul>
      </HintBox>

      <div className="mt-4 flex gap-2">
        <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50" onClick={reload} disabled={loading}>
          Обновить
        </button>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">PostgreSQL</div>
          <div className="mt-1">{overview ? statusBadge(overview.db_ok) : "—"}</div>
        </div>
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Redis</div>
          <div className="mt-1">{overview ? statusBadge(overview.redis_ok) : "—"}</div>
        </div>
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">RQ default queue</div>
          <div className="mt-1 text-sm">{overview ? overview.rq_default_queue_count : "—"}</div>
        </div>
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Alembic</div>
          <div className="mt-1 text-sm">{overview?.alembic_version || "—"}</div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Monitoring: critical</div>
          <div className="mt-1 text-lg font-semibold text-red-700">{overview?.alert_critical_count ?? 0}</div>
        </div>
        <div className="rounded border bg-white p-3">
          <div className="text-xs text-slate-500">Monitoring: warning</div>
          <div className="mt-1 text-lg font-semibold text-amber-700">{overview?.alert_warning_count ?? 0}</div>
        </div>
      </div>

      <div className="mt-4 rounded border bg-white">
        <div className="border-b px-3 py-2 text-sm font-semibold">Топ алертов мониторинга</div>
        <div className="max-h-64 overflow-auto">
          {alerts.length === 0 ? (
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

      <div className="mt-6 rounded border bg-white p-4">
        <div className="text-sm font-semibold">Прогон источника (enqueue)</div>
        <p className="mt-1 text-xs text-slate-600">Проверяет связку UI → API → Redis queue → worker (RQ job).</p>

        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto]">
          <select className="w-full rounded border px-3 py-2 text-sm" value={runSourceId} onChange={(e) => setRunSourceId(e.target.value)}>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {sourceLabel.get(s.id)}
              </option>
            ))}
          </select>
          <button
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
            disabled={!accessToken || !isAdmin || !runSourceId}
            onClick={async () => {
              if (!accessToken) return;
              setJobError(null);
              setJobStatus(null);
              setJobId(null);
              try {
                const res = await api.diagnostics.runSourceNow(accessToken, runSourceId);
                setJobId(res.job_id);
              } catch (e: any) {
                setJobError(e?.message || "Ошибка enqueue");
              }
            }}
          >
            Запустить сейчас
          </button>
        </div>

        {!isAdmin ? <div className="mt-2 text-xs text-amber-700">Требуется роль Admin.</div> : null}
        {jobError ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{jobError}</div> : null}

        {jobId ? (
          <div className="mt-3 rounded border bg-slate-50 p-3">
            <div className="text-xs text-slate-600">
              Job ID: <code className="rounded bg-white px-1">{jobId}</code>
            </div>
            <div className="mt-2 flex gap-2">
              <button
                className="rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-50"
                onClick={async () => {
                  if (!accessToken) return;
                  try {
                    const st = await api.diagnostics.jobStatus(accessToken, jobId);
                    setJobStatus(st);
                  } catch (e: any) {
                    setJobError(e?.message || "Ошибка статуса");
                  }
                }}
              >
                Обновить статус
              </button>
            </div>
            {jobStatus ? <pre className="mt-2 overflow-auto rounded border bg-white p-2 text-xs">{JSON.stringify(jobStatus, null, 2)}</pre> : null}
          </div>
        ) : null}
      </div>

      <div className="mt-6 rounded border bg-white p-4">
        <div className="text-sm font-semibold">Пересборка кластеров новостей (enqueue)</div>
        <p className="mt-1 text-xs text-slate-600">
          Группирует похожие материалы по simhash за последние ~90 дней. Нужно для раздела «Кластеры» в PDF/HTML после ИИ-обработки.
        </p>
        <div className="mt-3">
          <button
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
            disabled={!accessToken || !isAdmin}
            onClick={async () => {
              if (!accessToken) return;
              setClusterJobError(null);
              setClusterJobStatus(null);
              setClusterJobId(null);
              try {
                const res = await api.diagnostics.rebuildNewsClusters(accessToken);
                setClusterJobId(res.job_id);
              } catch (e: any) {
                setClusterJobError(e?.message || "Ошибка enqueue");
              }
            }}
          >
            Пересобрать кластеры
          </button>
        </div>
        {!isAdmin ? <div className="mt-2 text-xs text-amber-700">Требуется роль Admin.</div> : null}
        {clusterJobError ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{clusterJobError}</div> : null}
        {clusterJobId ? (
          <div className="mt-3 rounded border bg-slate-50 p-3">
            <div className="text-xs text-slate-600">
              Job ID: <code className="rounded bg-white px-1">{clusterJobId}</code>
            </div>
            <div className="mt-2 flex gap-2">
              <button
                className="rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-50"
                onClick={async () => {
                  if (!accessToken) return;
                  try {
                    const st = await api.diagnostics.jobStatus(accessToken, clusterJobId);
                    setClusterJobStatus(st);
                  } catch (e: any) {
                    setClusterJobError(e?.message || "Ошибка статуса");
                  }
                }}
              >
                Обновить статус
              </button>
            </div>
            {clusterJobStatus ? (
              <pre className="mt-2 overflow-auto rounded border bg-white p-2 text-xs">{JSON.stringify(clusterJobStatus, null, 2)}</pre>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-6 rounded border bg-white p-4">
        <div className="text-sm font-semibold">Рекомендуемый smoke-test (MVP)</div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li>Создать 7 регионов в “Регионы”.</li>
          <li>Создать 1 конкурента с алиасами в “Конкуренты”.</li>
          <li>Добавить RSS источник (тип RSS_ATOM) и привязать конкурента/регион.</li>
          <li>Зайти в “Мониторинг” и убедиться, что источник без ошибок (после прогона/работы scheduler).</li>
          <li>Опционально: создать HTML-шаблон и прогнать “Тест шаблона” на одной статье.</li>
        </ol>
        <div className="mt-2 text-xs text-slate-500">
          Примечание: источники RSS/HTML/TG парсятся worker’ом. Для Telegram нужно заранее авторизовать session-файл в `TELEGRAM_SESSION_DIR` (one-time).
        </div>
      </div>
    </div>
  );
}

