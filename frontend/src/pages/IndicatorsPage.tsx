import { useEffect, useMemo, useState } from "react";
import { FileUp, Trash2 } from "lucide-react";
import { api, type IndicatorHistoryOut, type IndicatorLatestOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

type ParsedRow = { indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null };

function formatRate(v: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 4 }).format(v);
}

function formatDate(s: string) {
  try {
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" }).format(new Date(s));
  } catch {
    return s;
  }
}

function formatDateTime(s: string) {
  try {
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(s));
  } catch {
    return s;
  }
}

export function IndicatorsPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();

  const [latest, setLatest] = useState<IndicatorLatestOut | null>(null);
  const [history, setHistory] = useState<IndicatorHistoryOut | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notCollectedYet, setNotCollectedYet] = useState(false);

  const [importOpen, setImportOpen] = useState(false);
  const [parsedRows, setParsedRows] = useState<ParsedRow[]>([]);
  const [parseLoading, setParseLoading] = useState(false);
  const [sourceName, setSourceName] = useState("");

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    setNotCollectedYet(false);
    try {
      const [l, h] = await Promise.all([api.indicators.cnyRubLatest(accessToken), api.indicators.cnyRubHistory(accessToken, days)]);
      setLatest(l);
      setHistory(h);
    } catch (e: any) {
      const msg = e?.message || "Ошибка загрузки индикаторов";
      if (msg.includes("not collected yet")) {
        setLatest(null);
        setHistory({ series: "CNY_RUB", unit: "RUB", items: [] });
        setNotCollectedYet(true);
      } else {
        setError(msg);
        push({ variant: "error", title: "Индикаторы", description: msg });
      }
    } finally {
      setLoading(false);
    }
  };

  const collectNow = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      await api.indicators.cnyRubCollectNow(accessToken);
      push({ variant: "success", title: "MOEX", description: "Курс обновлён" });
      await reload();
    } catch (e: any) {
      const msg = e?.message || "Не удалось собрать курс";
      setError(msg);
      push({ variant: "error", title: "MOEX", description: msg });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const handleParseFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !accessToken) return;
    setParseLoading(true);
    setError(null);
    try {
      const rows = await api.indicators.parseDocument(accessToken, file);
      setParsedRows(rows);
      setImportOpen(true);
    } catch (err: any) {
      push({ variant: "error", title: "Ошибка парсинга", description: err?.message || "Не удалось распознать файл" });
    } finally {
      setParseLoading(false);
      e.target.value = "";
    }
  };

  const handleSaveImport = async () => {
    if (!accessToken || parsedRows.length === 0) return;
    setParseLoading(true);
    try {
      const res = await api.indicators.importParsed(accessToken, {
        rows: parsedRows.map((r) => ({
          indicator_name: r.indicator_name,
          period: r.period,
          value: r.value,
          change_pct: r.change_pct ?? null,
          unit: r.unit ?? null,
        })),
        source_name: sourceName || null,
      });
      push({ variant: "success", title: "Импорт", description: `Сохранено: ${res.inserted} записей` });
      setParsedRows([]);
      setImportOpen(false);
    } catch (err: any) {
      push({ variant: "error", title: "Ошибка сохранения", description: err?.message || "Не удалось сохранить" });
    } finally {
      setParseLoading(false);
    }
  };

  const updateParsedRow = (idx: number, field: keyof ParsedRow, value: string | number | null) => {
    setParsedRows((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const removeParsedRow = (idx: number) => {
    setParsedRows((prev) => prev.filter((_, i) => i !== idx));
  };

  const changeAbs = useMemo(() => {
    const items = history?.items || [];
    if (items.length < 2) return null;
    const a = items[items.length - 2]?.value;
    const b = items[items.length - 1]?.value;
    if (typeof a !== "number" || typeof b !== "number") return null;
    return b - a;
  }, [history]);

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Индикаторы</h1>
          <p className="mt-1 text-sm text-slate-600">Макро-показатели и курсы. Источник курса CNY/RUB: MOEX (CNYRUB_TOM).</p>
          <HintBox>
            <div className="font-medium">Примечание</div>
            <div className="mt-1">
              Значение обновляется планировщиком (примерно раз в час). Если в БД ещё нет значений — дождитесь первого запуска scheduler/worker.
            </div>
          </HintBox>
        </div>
        <div className="flex flex-wrap gap-2">
          {user?.role === "Admin" ? (
            <button
              className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              onClick={collectNow}
              disabled={loading}
            >
              Собрать сейчас (MOEX)
            </button>
          ) : null}
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50" onClick={reload} disabled={loading}>
            Обновить
          </button>
        </div>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}
      {notCollectedYet ? (
        <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-800">
          Курс ещё не собран. Нажмите <b>“Собрать сейчас (MOEX)”</b> или дождитесь запуска scheduler/worker.
        </div>
      ) : null}

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="rounded border bg-white p-4 lg:col-span-2">
          <div className="text-xs text-slate-500">CNY → RUB</div>
          <div className="mt-1 flex items-end gap-3">
            <div className="text-3xl font-semibold">{latest ? formatRate(latest.value) : "—"}</div>
            <div className="pb-1 text-sm text-slate-600">RUB за 1 CNY</div>
          </div>
          <div className="mt-2 grid gap-1 text-xs text-slate-600">
            <div>
              Дата: <span className="font-medium text-slate-800">{latest ? formatDate(latest.period_date) : "—"}</span>
            </div>
            <div>
              Обновлено (fetched): <span className="font-medium text-slate-800">{latest ? formatDateTime(latest.fetched_at) : "—"}</span>
            </div>
            <div>
              Обновлено на бирже (MSK): <span className="font-medium text-slate-800">{latest?.updated_at_msk ? formatDateTime(latest.updated_at_msk) : "—"}</span>
            </div>
            <div>
              Источник: <span className="font-medium text-slate-800">{latest?.source_name || "—"}</span>
            </div>
          </div>
        </div>

        <div className="rounded border bg-white p-4">
          <div className="text-xs text-slate-500">Динамика</div>
          <div className="mt-2 text-sm text-slate-700">
            {changeAbs === null ? (
              <div className="text-slate-500">Недостаточно данных</div>
            ) : (
              <div>
                Изменение за день:{" "}
                <span className={`font-semibold ${changeAbs >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                  {changeAbs >= 0 ? "+" : ""}
                  {formatRate(changeAbs)}
                </span>
              </div>
            )}
          </div>
          <div className="mt-3">
            <label className="text-xs text-slate-600">Период истории</label>
            <select className="mt-1 w-full rounded border bg-white px-3 py-2 text-sm" value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>7 дней</option>
              <option value={30}>30 дней</option>
              <option value={90}>90 дней</option>
              <option value={180}>180 дней</option>
            </select>
          </div>
        </div>
      </div>

      {user?.role === "Admin" ? (
        <div className="mt-4 rounded-lg border-2 border-slate-200 bg-slate-50 p-4">
          <h2 className="text-base font-semibold text-slate-800">Импорт таблиц из PDF или скриншота</h2>
          <p className="mt-1 text-sm text-slate-600">
            Загрузите PDF или изображение (PNG, JPG) с таблицей показателей. Данные можно отредактировать перед сохранением в БД.
          </p>
          <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
            <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp" className="hidden" onChange={handleParseFile} disabled={parseLoading} />
            <FileUp className="h-4 w-4" />
            {parseLoading ? "Парсинг…" : "Выбрать файл"}
          </label>
        </div>
      ) : null}

      <div className="mt-4 overflow-x-auto rounded border bg-white">
        <table className="min-w-[520px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Дата</th>
              <th className="px-3 py-2">CNY→RUB</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={2}>
                  Загрузка…
                </td>
              </tr>
            ) : !history || history.items.length === 0 ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={2}>
                  Нет данных
                </td>
              </tr>
            ) : (
              [...history.items].reverse().map((p) => (
                <tr key={p.period_date} className="border-t">
                  <td className="px-3 py-2">{formatDate(p.period_date)}</td>
                  <td className="px-3 py-2 font-medium">{formatRate(p.value)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {importOpen && parsedRows.length > 0 ? (
        <div className="mt-6 rounded-lg border-2 border-amber-200 bg-amber-50/50 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-800">Редактирование перед сохранением</h2>
            <div className="flex gap-2">
              <input
                className="rounded border bg-white px-3 py-1.5 text-sm"
                placeholder="Источник (опционально)"
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
              />
              <button
                className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
                onClick={handleSaveImport}
                disabled={parseLoading}
              >
                Сохранить в БД
              </button>
              <button className="rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-50" onClick={() => setImportOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
          <p className="mt-1 text-xs text-slate-600">Отредактируйте данные при необходимости, затем нажмите «Сохранить в БД».</p>
          <div className="mt-3 max-h-[400px] overflow-auto rounded border bg-white">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-slate-50">
                <tr>
                  <th className="px-3 py-2">Показатель</th>
                  <th className="px-3 py-2">Период</th>
                  <th className="px-3 py-2">Значение</th>
                  <th className="px-3 py-2">Прирост %</th>
                  <th className="px-3 py-2">Ед.</th>
                  <th className="w-10 px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {parsedRows.map((r, idx) => (
                  <tr key={idx} className="border-t">
                    <td className="px-3 py-1.5">
                      <input
                        className="w-full min-w-[200px] rounded border bg-white px-2 py-1 text-sm"
                        value={r.indicator_name}
                        onChange={(e) => updateParsedRow(idx, "indicator_name", e.target.value)}
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        className="w-24 rounded border bg-white px-2 py-1 text-sm"
                        value={r.period}
                        onChange={(e) => updateParsedRow(idx, "period", e.target.value)}
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        type="number"
                        step="any"
                        className="w-24 rounded border bg-white px-2 py-1 text-sm"
                        value={r.value}
                        onChange={(e) => updateParsedRow(idx, "value", parseFloat(e.target.value) || 0)}
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        type="number"
                        step="any"
                        className="w-20 rounded border bg-white px-2 py-1 text-sm"
                        value={r.change_pct ?? ""}
                        onChange={(e) => updateParsedRow(idx, "change_pct", e.target.value === "" ? null : parseFloat(e.target.value) || 0)}
                        placeholder="—"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        className="w-24 rounded border bg-white px-2 py-1 text-sm"
                        value={r.unit ?? ""}
                        onChange={(e) => updateParsedRow(idx, "unit", e.target.value || "")}
                        placeholder="—"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <button type="button" onClick={() => removeParsedRow(idx)} className="text-red-600 hover:text-red-800">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

