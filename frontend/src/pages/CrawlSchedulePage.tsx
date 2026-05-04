import { useEffect, useState } from "react";
import { api, type SourceCrawlScheduleOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

function formatDt(s: string | null): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return s;
  }
}

export function CrawlSchedulePage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const canEnqueue = user?.role === "Admin" || user?.role === "Analyst";
  const [includeDisabled, setIncludeDisabled] = useState(false);
  const [serverNow, setServerNow] = useState<string | null>(null);
  const [dueCount, setDueCount] = useState(0);
  const [items, setItems] = useState<SourceCrawlScheduleOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.monitoring.crawlSchedule(accessToken, includeDisabled);
      setServerNow(res.server_now);
      setDueCount(res.due_count);
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
  }, [includeDisabled]);

  const handleEnqueueDue = async () => {
    if (!accessToken || !canEnqueue) return;
    try {
      const res = await api.monitoring.enqueueDue(accessToken);
      push({
        variant: "success",
        title: "Задачи поставлены в очередь",
        description: `Просроченных источников обработано: ${res.enqueued}. Воркер выполнит fetch_source.`,
      });
      await reload();
    } catch (e: any) {
      push({ variant: "error", title: "Не удалось поставить в очередь", description: e?.message || "Ошибка" });
    }
  };

  return (
    <div>
      <h1 className="text-lg font-semibold">Планировка обхода</h1>
      <p className="mt-1 text-sm text-slate-600">
        Когда планировщик сможет снова поставить источник в очередь (интервал и backoff). Совпадает с логикой фонового
        scheduler.
        {serverNow ? (
          <>
            {" "}
            Время сервера:{" "}
            <span className="whitespace-nowrap">{formatDt(serverNow)}</span>
          </>
        ) : null}
        {dueCount > 0 ? (
          <span className="ml-1 font-medium text-amber-800">· Просрочено сейчас: {dueCount}</span>
        ) : null}
      </p>
      <HintBox>
        <div className="font-medium">Как читать</div>
        <ul className="mt-1 list-disc pl-4">
          <li>
            <b>Просрочен</b> — источник включён, интервал с последнего обхода вышел, backoff не блокирует (как в
            планировщике).
          </li>
          <li>
            <b>След. в очередь</b> — когда ожидается следующая постановка задачи, если не запускать сбор вручную.
          </li>
          <li>
            Кнопка «Запустить просроченные» ставит в Redis/RQ те же задачи, что и фоновый цикл (роли Admin/Analyst).
          </li>
        </ul>
      </HintBox>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={includeDisabled} onChange={(e) => setIncludeDisabled(e.target.checked)} />
          Показывать отключённые источники
        </label>
        <div className="flex flex-wrap gap-2">
          {canEnqueue ? (
            <button
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
              type="button"
              onClick={handleEnqueueDue}
              disabled={loading}
            >
              Запустить просроченные
            </button>
          ) : null}
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" type="button" onClick={reload} disabled={loading}>
            Обновить
          </button>
        </div>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 overflow-x-auto rounded border bg-white">
        <table className="min-w-[1000px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Источник</th>
              <th className="px-3 py-2">Тип</th>
              <th className="px-3 py-2">Вкл.</th>
              <th className="px-3 py-2">Интервал, мин</th>
              <th className="px-3 py-2">Последний обход</th>
              <th className="px-3 py-2">Успех</th>
              <th className="px-3 py-2">Backoff до</th>
              <th className="px-3 py-2">Просрочен</th>
              <th className="px-3 py-2">След. в очередь</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={9}>
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={9}>
                  Нет источников.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className={`border-t ${row.is_due ? "bg-amber-50/80" : ""}`}>
                  <td className="max-w-[240px] px-3 py-2 font-medium whitespace-normal break-words">{row.display_label}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-slate-600">{row.source_type}</td>
                  <td className="px-3 py-2">{row.enabled ? "да" : "нет"}</td>
                  <td className="px-3 py-2">{row.fetch_frequency_min}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDt(row.last_fetch_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDt(row.last_success_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDt(row.backoff_until)}</td>
                  <td className="px-3 py-2 font-medium">{row.is_due ? "да" : "нет"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDt(row.next_expected_enqueue_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
