import { useCallback, useEffect, useMemo, useState } from "react";
import { FileUp, Pencil, Plus, Trash2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList } from "recharts";
import {
  api,
  type IndicatorHistoryOut,
  type IndicatorLatestOut,
  type IndicatorTelegramConfigOut,
  type IndicatorTelegramPostOut,
  type IndicatorTelegramReportGroup,
  type ParsedIndicatorOut,
} from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

type ParsedRow = { indicator_name: string; period: string; value: number; change_pct?: number | null; unit?: string | null };

function roundTo(value: number, digits: number = 2): number {
  const p = 10 ** digits;
  return Math.round(value * p) / p;
}

function changeToneClass(delta: number): string {
  if (delta > 0) return "bg-red-50 text-red-700";
  if (delta < 0) return "bg-emerald-50 text-emerald-700";
  return "bg-slate-100 text-slate-700";
}

function withAutoChangePct(rows: ParsedRow[]): ParsedRow[] {
  const out = rows.map((r) => ({ ...r }));
  const byIndicator = new Map<string, Array<{ idx: number; row: ParsedRow }>>();

  out.forEach((row, idx) => {
    const key = (row.indicator_name || "").trim().toLowerCase();
    if (!byIndicator.has(key)) byIndicator.set(key, []);
    byIndicator.get(key)!.push({ idx, row });
  });

  for (const entries of byIndicator.values()) {
    entries.sort((a, b) => {
      const ka = periodSortKey(a.row.period);
      const kb = periodSortKey(b.row.period);
      return ka - kb;
    });
    for (let i = 0; i < entries.length; i++) {
      const cur = entries[i];
      const prev = entries[i - 1];
      if (!prev || !Number.isFinite(prev.row.value) || prev.row.value === 0) {
        out[cur.idx].change_pct = null;
        continue;
      }
      const deltaPct = ((cur.row.value - prev.row.value) / Math.abs(prev.row.value)) * 100;
      out[cur.idx].change_pct = roundTo(deltaPct);
    }
  }
  return out;
}

function periodSortKey(periodRaw: string): number {
  const src = (periodRaw || "").replace(/\u00a0/g, " ").trim();
  if (!src) return Number.MAX_SAFE_INTEGER;
  const firstPart = src.split(/\s*[-–—]\s*/)[0]?.trim() || src;
  const s = firstPart.toLowerCase().replace(/\s+г\.?$/, "").trim();

  const months: Record<string, number> = {
    января: 1, янв: 1,
    февраля: 2, фев: 2,
    марта: 3, мар: 3,
    апреля: 4, апр: 4,
    мая: 5, май: 5,
    июня: 6, июн: 6,
    июля: 7, июл: 7,
    августа: 8, авг: 8,
    сентября: 9, сен: 9,
    октября: 10, окт: 10,
    ноября: 11, ноя: 11,
    декабря: 12, дек: 12,
  };

  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getTime();
  m = s.match(/^(\d{4})-(\d{1,2})$/);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, 1).getTime();
  m = s.match(/^(\d{4})$/);
  if (m) return new Date(Number(m[1]), 0, 1).getTime();

  m = s.match(/(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\.?\s*(\d{4})/);
  if (m) return new Date(Number(m[2]), months[m[1]] - 1, 1).getTime();

  const dm = s.match(/^(\d{1,2})\s+([а-яё.]+)\s+(\d{4})$/i);
  if (dm) {
    const day = Number(dm[1]);
    const monToken = dm[2].replace(".", "");
    const month = months[monToken] ?? 1;
    const year = Number(dm[3]);
    return new Date(year, month - 1, day).getTime();
  }

  return Number.MAX_SAFE_INTEGER;
}

function sortByPeriod<T extends { period: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const ka = periodSortKey(a.period);
    const kb = periodSortKey(b.period);
    if (ka !== kb) return ka - kb;
    return a.period.localeCompare(b.period, "ru");
  });
}

function compactPeriodLabel(period: string): string {
  const ts = periodSortKey(period);
  if (Number.isFinite(ts) && ts < Number.MAX_SAFE_INTEGER) {
    return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" }).format(new Date(ts));
  }
  return period;
}

function formatValue(v: number, unit?: string | null) {
  const s = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 4 }).format(v);
  return unit ? `${s} ${unit}` : s;
}

function formatDate(s: string) {
  try {
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" }).format(new Date(s));
  } catch {
    return s;
  }
}

function parseKeywords(s: string): string[] {
  return s
    .split(/[\n,;]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function keywordsToText(list: string[]): string {
  return (list || []).join("\n");
}

function formatDateTime(s: string) {
  try {
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(s));
  } catch {
    return s;
  }
}

function IndicatorChartCard({
  id,
  title,
  subtitle,
  unit,
  items,
  formatVal = (v: number) => formatValue(v),
}: {
  id: string;
  title: string;
  subtitle?: string;
  unit?: string | null;
  items: Array<{ period: string; value: number }>;
  formatVal?: (v: number) => string;
}) {
  if (items.length === 0) return null;
  const chartData = items.map((p) => ({ date: p.period, value: p.value, label: p.period }));
  const latest = items[items.length - 1];
  const prev = items.length >= 2 ? items[items.length - 2] : null;
  const change = prev ? latest.value - prev.value : null;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/50 px-5 py-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-slate-800">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-2xl font-semibold tabular-nums text-slate-900">{formatVal(latest.value)}</div>
            <div className="text-xs text-slate-500">{latest.period}</div>
          </div>
          {change !== null ? (
            <div className={`rounded-lg px-3 py-1.5 text-sm font-medium tabular-nums ${changeToneClass(change)}`}>
              {change >= 0 ? "+" : ""}
              {formatVal(change)}
            </div>
          ) : null}
        </div>
      </div>
      <div className="p-5">
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
              <defs>
                <linearGradient id={`lineGrad-${id}`} x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#0f172a" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#475569" stopOpacity={0.7} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#64748b" }} tickFormatter={(v) => compactPeriodLabel(String(v))} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: "#64748b" }} tickFormatter={(v) => formatVal(v)} domain={["auto", "auto"]} axisLine={false} tickLine={false} width={56} />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                formatter={(v) => [formatVal(Number(v ?? 0)), unit || ""]}
                labelFormatter={(l) => String(l ?? "")}
              />
              <Line type="monotone" dataKey="value" stroke={`url(#lineGrad-${id})`} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 6, fill: "#0f172a", stroke: "#fff", strokeWidth: 2 }}>
                <LabelList dataKey="value" position="top" formatter={(v) => formatVal(Number(v ?? 0))} className="fill-slate-500 text-[10px]" />
              </Line>
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export function IndicatorsPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();

  const [latest, setLatest] = useState<IndicatorLatestOut | null>(null);
  const [cnyHistory, setCnyHistory] = useState<IndicatorHistoryOut | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notCollectedYet, setNotCollectedYet] = useState(false);

  const [parsedNames, setParsedNames] = useState<string[]>([]);
  const [parsedHistory, setParsedHistory] = useState<Record<string, Array<{ period: string; value: number; unit?: string | null }>>>({});
  const [parsedItems, setParsedItems] = useState<ParsedIndicatorOut[]>([]);

  const [importOpen, setImportOpen] = useState(false);
  const [parsedRows, setParsedRows] = useState<ParsedRow[]>([]);
  const [parseLoading, setParseLoading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [sourceName, setSourceName] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({ indicator_name: "", period: "", value: 0, change_pct: null as number | null, unit: "", source_name: "" });
  const [addBusy, setAddBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editBusy, setEditBusy] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ indicator_name: "", period: "", value: 0, change_pct: null as number | null, unit: "", source_name: "" });
  const [keyRateForm, setKeyRateForm] = useState({
    period: new Date().toISOString().slice(0, 10),
    value: "",
    source_name: "Ручной ввод",
  });
  const [keyRateBusy, setKeyRateBusy] = useState(false);

  const [tgConfig, setTgConfig] = useState<IndicatorTelegramConfigOut | null>(null);
  const [tgPosts, setTgPosts] = useState<IndicatorTelegramPostOut[]>([]);
  const [tgForm, setTgForm] = useState({
    enabled: false,
    channel_username: "",
    include_keywords: "",
    exclude_keywords: "",
    match_whole_words: false,
    backfill_limit: 100,
    include_in_report: true,
    ai_in_report: false,
    report_groups: [
      { title: "Ввод жилья", keywords: "ввод жилья" },
      { title: "Ввод МКД", keywords: "многоквартирных\nмкд" },
    ] as Array<{ title: string; keywords: string }>,
  });
  const [tgConfigBusy, setTgConfigBusy] = useState(false);
  const [tgCollectBusy, setTgCollectBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    setNotCollectedYet(false);
    try {
      const [l, h, names, list, tgCfg, tgList] = await Promise.all([
        api.indicators.cnyRubLatest(accessToken).catch(() => null),
        api.indicators.cnyRubHistory(accessToken, days).catch((e: any) => (e?.message?.includes("not collected") ? { series: "CNY_RUB", unit: "RUB", items: [] } : Promise.reject(e))),
        api.indicators.parsedNames(accessToken),
        api.indicators.parsedList(accessToken),
        api.indicators.telegramConfig.get(accessToken),
        api.indicators.telegramConfig.posts(accessToken, { limit: 60 }),
      ]);
      setLatest(l || null);
      setCnyHistory(h);
      if (h?.items?.length === 0) setNotCollectedYet(true);
      setParsedNames(names);
      setParsedItems(list.items);
      setTgConfig(tgCfg);
      setTgPosts(tgList.items);
      setTgForm({
        enabled: tgCfg.enabled,
        channel_username: tgCfg.channel_username,
        include_keywords: keywordsToText(tgCfg.include_keywords),
        exclude_keywords: keywordsToText(tgCfg.exclude_keywords),
        match_whole_words: tgCfg.match_whole_words,
        backfill_limit: tgCfg.backfill_limit,
        include_in_report: tgCfg.include_in_report ?? true,
        ai_in_report: tgCfg.ai_in_report ?? false,
        report_groups: (tgCfg.report_groups?.length
          ? tgCfg.report_groups
          : [
              { title: "Ввод жилья", keywords: ["ввод жилья"] },
              { title: "Ввод МКД", keywords: ["многоквартирных", "мкд"] },
            ]
        ).map((g) => ({ title: g.title, keywords: keywordsToText(g.keywords) })),
      });

      const hist: Record<string, Array<{ period: string; value: number; unit?: string | null }>> = {};
      for (const name of names) {
        try {
          const res = await api.indicators.parsedHistory(accessToken, name);
          hist[name] = sortByPeriod(res.items);
        } catch {
          hist[name] = [];
        }
      }
      setParsedHistory(hist);
    } catch (e: any) {
      const msg = e?.message || "Ошибка загрузки";
      setError(msg);
      push({ variant: "error", title: "Индикаторы", description: msg });
    } finally {
      setLoading(false);
    }
  }, [accessToken, days, push]);

  useEffect(() => {
    reload();
  }, [reload]);

  const saveTgConfig = async () => {
    if (!accessToken) return;
    setTgConfigBusy(true);
    try {
      const report_groups: IndicatorTelegramReportGroup[] = tgForm.report_groups
        .map((g) => ({
          title: g.title.trim(),
          keywords: parseKeywords(g.keywords),
        }))
        .filter((g) => g.title && g.keywords.length > 0);
      const updated = await api.indicators.telegramConfig.update(accessToken, {
        enabled: tgForm.enabled,
        channel_username: tgForm.channel_username.trim().replace(/^@/, ""),
        include_keywords: parseKeywords(tgForm.include_keywords),
        exclude_keywords: parseKeywords(tgForm.exclude_keywords),
        match_whole_words: tgForm.match_whole_words,
        backfill_limit: tgForm.backfill_limit,
        include_in_report: tgForm.include_in_report,
        ai_in_report: tgForm.ai_in_report,
        report_groups,
      });
      setTgConfig(updated);
      push({ variant: "success", title: "Telegram", description: "Настройки сохранены" });
    } catch (e: any) {
      push({ variant: "error", title: "Telegram", description: e?.message || "Не удалось сохранить" });
    } finally {
      setTgConfigBusy(false);
    }
  };

  const collectTgNow = async () => {
    if (!accessToken) return;
    setTgCollectBusy(true);
    try {
      const res = await api.indicators.telegramConfig.collectNow(accessToken);
      push({
        variant: "success",
        title: "Telegram",
        description: `Собрано: ${res.matched ?? 0} из ${res.fetched ?? 0}, новых ${res.inserted ?? 0}`,
      });
      await reload();
    } catch (e: any) {
      push({ variant: "error", title: "Telegram", description: e?.message || "Ошибка сбора" });
    } finally {
      setTgCollectBusy(false);
    }
  };

  const collectNow = async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      await api.indicators.cnyRubCollectNow(accessToken);
      push({ variant: "success", title: "MOEX", description: "Курс обновлён" });
      await reload();
    } catch (e: any) {
      push({ variant: "error", title: "MOEX", description: e?.message || "Не удалось собрать" });
    } finally {
      setLoading(false);
    }
  };

  const handleParseFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !accessToken) return;
    setParseLoading(true);
    setParseError(null);
    try {
      const rows = await api.indicators.parseDocument(accessToken, file);
      setParsedRows(withAutoChangePct(rows));
      setImportOpen(true);
      setParseError(rows.length === 0 ? "В файле не найдено табличных данных." : null);
    } catch (err: any) {
      setParseError(err?.message || "Не удалось распознать файл");
      push({ variant: "error", title: "Ошибка парсинга", description: err?.message });
    } finally {
      setParseLoading(false);
      e.target.value = "";
    }
  };

  const handleSaveImport = async () => {
    if (!accessToken || parsedRows.length === 0) return;
    setParseLoading(true);
    try {
      await api.indicators.importParsed(accessToken, {
        rows: parsedRows.map((r) => ({ indicator_name: r.indicator_name, period: r.period, value: r.value, change_pct: r.change_pct ?? null, unit: r.unit ?? null })),
        source_name: sourceName || null,
      });
      push({ variant: "success", title: "Импорт", description: `Сохранено: ${parsedRows.length} записей` });
      setParsedRows([]);
      setImportOpen(false);
      await reload();
    } catch (err: any) {
      push({ variant: "error", title: "Ошибка", description: err?.message });
    } finally {
      setParseLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!accessToken || !addForm.indicator_name.trim() || !addForm.period.trim()) return;
    setAddBusy(true);
    try {
      await api.indicators.parsedCreate(accessToken, {
        indicator_name: addForm.indicator_name.trim(),
        period: addForm.period.trim(),
        value: addForm.value,
        change_pct: addForm.change_pct,
        unit: addForm.unit || null,
        source_name: addForm.source_name || null,
      });
      push({ variant: "success", title: "Добавлено", description: "Индикатор сохранён" });
      setAddForm({ indicator_name: "", period: "", value: 0, change_pct: null, unit: "", source_name: "" });
      setAddOpen(false);
      await reload();
    } catch (err: any) {
      push({ variant: "error", title: "Ошибка", description: err?.message });
    } finally {
      setAddBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!accessToken || !confirm("Удалить запись?")) return;
    try {
      await api.indicators.parsedDelete(accessToken, id);
      push({ variant: "success", title: "Удалено", description: "Запись удалена" });
      await reload();
    } catch (err: any) {
      push({ variant: "error", title: "Ошибка", description: err?.message });
    }
  };

  const handleEditOpen = (row: ParsedIndicatorOut) => {
    setEditId(row.id);
    setEditForm({
      indicator_name: row.indicator_name,
      period: row.period,
      value: row.value,
      change_pct: row.change_pct,
      unit: row.unit || "",
      source_name: row.source_name || "",
    });
    setEditOpen(true);
  };

  const handleEditSave = async () => {
    if (!accessToken || !editId || !editForm.indicator_name.trim() || !editForm.period.trim()) return;
    setEditBusy(true);
    try {
      await api.indicators.parsedUpdate(accessToken, editId, {
        indicator_name: editForm.indicator_name.trim(),
        period: editForm.period.trim(),
        value: editForm.value,
        change_pct: editForm.change_pct,
        unit: editForm.unit || null,
        source_name: editForm.source_name || null,
      });
      push({ variant: "success", title: "Обновлено", description: "Запись индикатора обновлена" });
      setEditOpen(false);
      setEditId(null);
      await reload();
    } catch (err: any) {
      push({ variant: "error", title: "Ошибка", description: err?.message || "Не удалось обновить запись" });
    } finally {
      setEditBusy(false);
    }
  };

  const handleAddKeyRate = async () => {
    if (!accessToken || !keyRateForm.period || keyRateForm.value.trim() === "") return;
    const valueNum = Number(keyRateForm.value.replace(",", "."));
    if (Number.isNaN(valueNum)) {
      push({ variant: "error", title: "Ключевая ставка", description: "Введите корректное число" });
      return;
    }
    setKeyRateBusy(true);
    try {
      await api.indicators.parsedCreate(accessToken, {
        indicator_name: "Ключевая ставка",
        period: keyRateForm.period,
        value: valueNum,
        change_pct: null,
        unit: "%",
        source_name: keyRateForm.source_name || "Ручной ввод",
      });
      push({ variant: "success", title: "Ключевая ставка", description: "Запись добавлена, график обновлён" });
      setKeyRateForm((prev) => ({ ...prev, value: "" }));
      await reload();
    } catch (err: any) {
      push({ variant: "error", title: "Ключевая ставка", description: err?.message || "Не удалось сохранить" });
    } finally {
      setKeyRateBusy(false);
    }
  };

  const updateParsedRow = (idx: number, field: keyof ParsedRow, value: string | number | null) => {
    setParsedRows((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      if (field === "change_pct") return next;
      return withAutoChangePct(next);
    });
  };

  const removeParsedRow = (idx: number) => {
    setParsedRows((prev) => withAutoChangePct(prev.filter((_, i) => i !== idx)));
  };

  const autoChangeById = useMemo(() => {
    const map = new Map<string, number | null>();
    const grouped = new Map<string, ParsedIndicatorOut[]>();
    for (const r of parsedItems) {
      const key = (r.indicator_name || "").trim().toLowerCase();
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(r);
    }
    for (const rows of grouped.values()) {
      const sorted = [...rows].sort((a, b) => periodSortKey(a.period) - periodSortKey(b.period));
      for (let i = 0; i < sorted.length; i++) {
        const cur = sorted[i];
        const prev = sorted[i - 1];
        if (!prev || !Number.isFinite(prev.value) || prev.value === 0) {
          map.set(cur.id, null);
          continue;
        }
        map.set(cur.id, roundTo(((cur.value - prev.value) / Math.abs(prev.value)) * 100));
      }
    }
    return map;
  }, [parsedItems]);

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Индикаторы</h1>
          <p className="mt-1 text-sm text-slate-600">Макро-показатели и курсы. CNY/RUB — MOEX. Остальные — импорт из PDF/таблицы.</p>
          <HintBox>
            <div className="font-medium">Источники</div>
            <div className="mt-1">CNY/RUB обновляется планировщиком. Ключевая ставка и др. — добавляйте вручную или импортируйте из PDF.</div>
          </HintBox>
        </div>
        <div className="flex flex-wrap gap-2">
          {user?.role === "Admin" ? (
            <>
              <button className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50" onClick={collectNow} disabled={loading}>
                Собрать CNY (MOEX)
              </button>
              <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" onClick={() => setAddOpen(true)}>
                <Plus className="mr-1 inline h-4 w-4" />
                Добавить
              </button>
            </>
          ) : null}
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" onClick={reload} disabled={loading}>
            Обновить
          </button>
        </div>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-6 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Telegram для индикаторов</h2>
            <p className="mt-1 text-sm text-slate-600">
              Посты из канала по ключевым словам: первая картинка и текст. Нужна авторизация в разделе «Telegram-парсер».
            </p>
            {tgConfig?.last_fetch_at ? (
              <p className="mt-1 text-xs text-slate-500">
                Последний сбор: {formatDateTime(tgConfig.last_fetch_at)}
                {tgConfig.last_error ? ` · ошибка: ${tgConfig.last_error}` : ""}
              </p>
            ) : null}
          </div>
          {user?.role === "Admin" ? (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                onClick={saveTgConfig}
                disabled={tgConfigBusy}
              >
                Сохранить настройки
              </button>
              <button
                type="button"
                className="rounded bg-sky-700 px-3 py-2 text-sm text-white hover:bg-sky-800 disabled:opacity-50"
                onClick={collectTgNow}
                disabled={tgCollectBusy || !tgForm.enabled}
              >
                {tgCollectBusy ? "Сбор…" : "Собрать из Telegram"}
              </button>
            </div>
          ) : null}
        </div>

        {user?.role === "Admin" ? (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex items-center gap-2 md:col-span-2">
              <input
                type="checkbox"
                checked={tgForm.enabled}
                onChange={(e) => setTgForm((f) => ({ ...f, enabled: e.target.checked }))}
              />
              <span className="text-sm">Включить автосбор (планировщик)</span>
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Канал (@username)</span>
              <input
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
                placeholder="erzrf"
                value={tgForm.channel_username}
                onChange={(e) => setTgForm((f) => ({ ...f, channel_username: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Лимит сообщений за проход</span>
              <input
                type="number"
                min={10}
                max={500}
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
                value={tgForm.backfill_limit}
                onChange={(e) => setTgForm((f) => ({ ...f, backfill_limit: Number(e.target.value) || 100 }))}
              />
            </label>
            <label className="block md:col-span-2">
              <span className="text-xs text-slate-600">Включить (хотя бы одно слово)</span>
              <textarea
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
                rows={2}
                placeholder="ввод жилья, многоквартирных"
                value={tgForm.include_keywords}
                onChange={(e) => setTgForm((f) => ({ ...f, include_keywords: e.target.value }))}
              />
            </label>
            <label className="block md:col-span-2">
              <span className="text-xs text-slate-600">Исключить</span>
              <textarea
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
                rows={2}
                value={tgForm.exclude_keywords}
                onChange={(e) => setTgForm((f) => ({ ...f, exclude_keywords: e.target.value }))}
              />
            </label>
            <label className="flex items-center gap-2 md:col-span-2">
              <input
                type="checkbox"
                checked={tgForm.match_whole_words}
                onChange={(e) => setTgForm((f) => ({ ...f, match_whole_words: e.target.checked }))}
              />
              <span className="text-sm">Целые слова</span>
            </label>
            <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-medium text-slate-800">В отчёте (HTML / PDF)</p>
              <p className="mt-1 text-xs text-slate-600">
                Посты попадают в раздел «Индикаторы» с картинкой и текстом. По умолчанию без ИИ — в посте уже есть анализ.
              </p>
              <label className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={tgForm.include_in_report}
                  onChange={(e) => setTgForm((f) => ({ ...f, include_in_report: e.target.checked }))}
                />
                <span className="text-sm">Включать в отчёт</span>
              </label>
              <label className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={tgForm.ai_in_report}
                  onChange={(e) => setTgForm((f) => ({ ...f, ai_in_report: e.target.checked }))}
                  disabled={!tgForm.include_in_report}
                />
                <span className="text-sm">Дополнительно обрабатывать через ИИ</span>
              </label>
            </div>
            {tgForm.report_groups.map((g, idx) => (
              <div key={idx} className="md:col-span-2 grid grid-cols-1 gap-2 rounded-lg border border-slate-200 p-3 md:grid-cols-2">
                <label className="block">
                  <span className="text-xs text-slate-600">Блок в отчёте</span>
                  <input
                    className="mt-1 w-full rounded border px-3 py-2 text-sm"
                    value={g.title}
                    onChange={(e) =>
                      setTgForm((f) => {
                        const groups = [...f.report_groups];
                        groups[idx] = { ...groups[idx], title: e.target.value };
                        return { ...f, report_groups: groups };
                      })
                    }
                  />
                </label>
                <label className="block md:col-span-1">
                  <span className="text-xs text-slate-600">Ключи для этого блока</span>
                  <textarea
                    className="mt-1 w-full rounded border px-3 py-2 text-sm"
                    rows={2}
                    value={g.keywords}
                    onChange={(e) =>
                      setTgForm((f) => {
                        const groups = [...f.report_groups];
                        groups[idx] = { ...groups[idx], keywords: e.target.value };
                        return { ...f, report_groups: groups };
                      })
                    }
                  />
                </label>
              </div>
            ))}
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {tgPosts.length === 0 ? (
            <p className="text-sm text-slate-500 sm:col-span-2 xl:col-span-3">Нет постов. Настройте канал и ключи, затем нажмите «Собрать из Telegram».</p>
          ) : (
            tgPosts.map((p) => (
              <article key={p.id} className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                {p.image_path ? (
                  <a href={p.post_url} target="_blank" rel="noopener noreferrer">
                    <img src={p.image_path} alt="" className="max-h-64 w-full object-cover bg-white" loading="lazy" />
                  </a>
                ) : (
                  <div className="flex h-32 items-center justify-center bg-slate-200 text-xs text-slate-500">Без изображения</div>
                )}
                <div className="space-y-2 p-3">
                  <div className="text-xs text-slate-500">
                    @{p.channel_username}
                    {p.published_at ? ` · ${formatDateTime(p.published_at)}` : ""}
                  </div>
                  {p.text ? <p className="text-sm text-slate-800 whitespace-pre-wrap line-clamp-6">{p.text}</p> : null}
                  {p.matched_keywords?.length ? (
                    <div className="flex flex-wrap gap-1">
                      {p.matched_keywords.map((k) => (
                        <span key={k} className="rounded bg-sky-100 px-1.5 py-0.5 text-xs text-sky-800">
                          {k}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <a href={p.post_url} target="_blank" rel="noopener noreferrer" className="text-xs text-sky-700 underline">
                    Открыть в Telegram
                  </a>
                </div>
              </article>
            ))
          )}
        </div>
      </div>

      {notCollectedYet ? (
        <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-800">
          Курс CNY ещё не собран. Нажмите <b>«Собрать CNY (MOEX)»</b> или дождитесь планировщика.
        </div>
      ) : null}

      {user?.role === "Admin" ? (
        <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <div className="text-sm font-medium text-slate-700">Ручной ввод ключевой ставки</div>
              <div className="mt-0.5 text-xs text-slate-500">Добавляет точку в индикатор "Ключевая ставка" и обновляет график.</div>
            </div>
            <label className="block">
              <span className="text-xs text-slate-600">Дата</span>
              <input
                type="date"
                className="mt-1 rounded border px-3 py-2 text-sm"
                value={keyRateForm.period}
                onChange={(e) => setKeyRateForm((f) => ({ ...f, period: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Ставка, %</span>
              <input
                type="number"
                step="0.01"
                className="mt-1 w-32 rounded border px-3 py-2 text-sm"
                value={keyRateForm.value}
                onChange={(e) => setKeyRateForm((f) => ({ ...f, value: e.target.value }))}
                placeholder="21"
              />
            </label>
            <button
              className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              onClick={handleAddKeyRate}
              disabled={keyRateBusy || !keyRateForm.period || keyRateForm.value.trim() === ""}
            >
              {keyRateBusy ? "Сохранение…" : "Добавить в график"}
            </button>
          </div>
        </div>
      ) : null}

      {/* CNY → RUB */}
      {cnyHistory && cnyHistory.items.length > 0 ? (
        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/50 px-5 py-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-slate-800">Курс CNY → RUB</h2>
              <p className="mt-0.5 text-sm text-slate-500">MOEX CNYRUB_TOM · {cnyHistory.unit || "RUB"} за 1 CNY</p>
            </div>
            <div className="flex items-center gap-4">
              {latest ? (
                <>
                  <div className="text-right">
                    <div className="text-2xl font-semibold tabular-nums text-slate-900">{formatValue(latest.value)}</div>
                    <div className="text-xs text-slate-500">{formatDate(latest.period_date)}</div>
                  </div>
                  {cnyHistory.items.length >= 2 ? (
                    <div
                      className={`rounded-lg px-3 py-1.5 text-sm font-medium tabular-nums ${
                        changeToneClass((cnyHistory.items[cnyHistory.items.length - 1]?.value ?? 0) - (cnyHistory.items[cnyHistory.items.length - 2]?.value ?? 0))
                      }`}
                    >
                      {((cnyHistory.items[cnyHistory.items.length - 1]?.value ?? 0) - (cnyHistory.items[cnyHistory.items.length - 2]?.value ?? 0) >= 0 ? "+" : "")}
                      {formatValue((cnyHistory.items[cnyHistory.items.length - 1]?.value ?? 0) - (cnyHistory.items[cnyHistory.items.length - 2]?.value ?? 0))}
                    </div>
                  ) : null}
                </>
              ) : null}
              <select className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>7 дней</option>
                <option value={30}>30 дней</option>
                <option value={90}>90 дней</option>
                <option value={180}>180 дней</option>
              </select>
            </div>
          </div>
          <div className="p-5">
            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cnyHistory.items.map((p) => ({ date: p.period_date, value: p.value }))} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
                  <defs>
                    <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#0f172a" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#475569" stopOpacity={0.7} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#64748b" }} tickFormatter={(v) => formatDate(v)} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
                  <YAxis tick={{ fontSize: 12, fill: "#64748b" }} tickFormatter={(v) => formatValue(v)} domain={["auto", "auto"]} axisLine={false} tickLine={false} width={56} />
                  <Tooltip
                    contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                    formatter={(v) => [formatValue(Number(v ?? 0)), "RUB"]}
                    labelFormatter={(l) => formatDate(String(l ?? ""))}
                  />
                  <Line type="monotone" dataKey="value" stroke="url(#lineGradient)" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 6, fill: "#0f172a", stroke: "#fff", strokeWidth: 2 }}>
                    <LabelList dataKey="value" position="top" formatter={(v) => formatValue(Number(v ?? 0))} className="fill-slate-500 text-[10px]" />
                  </Line>
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white p-8 text-center shadow-sm">
          <div className="text-slate-500">{loading ? "Загрузка…" : "Нет данных CNY. Соберите курс или дождитесь планировщика."}</div>
        </div>
      )}

      {/* Parsed indicators — charts (2+ points) or single-value card */}
      {parsedNames.map((name) => {
        const items = sortByPeriod(parsedHistory[name] || []);
        const unit = items[0]?.unit;
        if (items.length >= 2) {
          return (
            <div key={name} className="mt-4">
              <IndicatorChartCard id={name.replace(/\s/g, "-")} title={name} unit={unit} items={items} formatVal={(v) => formatValue(v, unit)} />
            </div>
          );
        }
        if (items.length === 1) {
          return (
            <div key={name} className="mt-4 overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-800">{name}</h2>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{formatValue(items[0].value, unit)}</p>
              <p className="mt-0.5 text-sm text-slate-500">{items[0].period}</p>
            </div>
          );
        }
        return null;
      })}

      {/* Table: all parsed indicators */}
      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-800">Все индикаторы (таблица)</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Показатель</th>
                <th className="px-4 py-3">Период</th>
                <th className="px-4 py-3">Значение</th>
                <th className="px-4 py-3">Прирост %</th>
                <th className="px-4 py-3">Ед.</th>
                <th className="px-4 py-3">Источник</th>
                {user?.role === "Admin" ? <th className="w-12 px-4 py-3"></th> : null}
              </tr>
            </thead>
            <tbody>
              {parsedItems.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={user?.role === "Admin" ? 7 : 6}>
                    Нет данных. Добавьте вручную или импортируйте из PDF.
                  </td>
                </tr>
              ) : (
                parsedItems.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                    <td className="px-4 py-2 font-medium">{r.indicator_name}</td>
                    <td className="px-4 py-2">{r.period}</td>
                    <td className="px-4 py-2 tabular-nums">{formatValue(r.value, r.unit)}</td>
                    <td className="px-4 py-2 tabular-nums">{(r.change_pct ?? autoChangeById.get(r.id) ?? null) != null ? `${(r.change_pct ?? autoChangeById.get(r.id) ?? null)}%` : "—"}</td>
                    <td className="px-4 py-2">{r.unit || "—"}</td>
                    <td className="px-4 py-2 text-slate-500">{r.source_name || "—"}</td>
                    {user?.role === "Admin" ? (
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-1">
                          <button type="button" onClick={() => handleEditOpen(r)} className="rounded p-1.5 text-slate-600 hover:bg-slate-100" title="Редактировать">
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button type="button" onClick={() => handleDelete(r.id)} className="rounded p-1.5 text-red-600 hover:bg-red-50" title="Удалить">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add form modal */}
      {addOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => !addBusy && setAddOpen(false)}>
          <div className="w-full max-w-md rounded-2xl border bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold">Добавить индикатор</h3>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="text-sm text-slate-600">Показатель</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={addForm.indicator_name} onChange={(e) => setAddForm((f) => ({ ...f, indicator_name: e.target.value }))} placeholder="Ключевая ставка" />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Период</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={addForm.period} onChange={(e) => setAddForm((f) => ({ ...f, period: e.target.value }))} placeholder="2024-01 или Янв. 2024" />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Значение</span>
                <input type="number" step="any" className="mt-1 w-full rounded border px-3 py-2" value={addForm.value || ""} onChange={(e) => setAddForm((f) => ({ ...f, value: parseFloat(e.target.value) || 0 }))} />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Прирост % (опц.)</span>
                <input type="number" step="any" className="mt-1 w-full rounded border px-3 py-2" value={addForm.change_pct ?? ""} onChange={(e) => setAddForm((f) => ({ ...f, change_pct: e.target.value === "" ? null : parseFloat(e.target.value) || 0 }))} placeholder="—" />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Ед. изм. (опц.)</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={addForm.unit} onChange={(e) => setAddForm((f) => ({ ...f, unit: e.target.value }))} placeholder="%" />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Источник (опц.)</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={addForm.source_name} onChange={(e) => setAddForm((f) => ({ ...f, source_name: e.target.value }))} placeholder="ЦБ РФ" />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button className="rounded border px-4 py-2 text-sm" onClick={() => setAddOpen(false)} disabled={addBusy}>
                Отмена
              </button>
              <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50" onClick={handleAdd} disabled={addBusy || !addForm.indicator_name.trim() || !addForm.period.trim()}>
                {addBusy ? "Сохранение…" : "Добавить"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Edit form modal */}
      {editOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => !editBusy && setEditOpen(false)}>
          <div className="w-full max-w-md rounded-2xl border bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold">Редактировать индикатор</h3>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="text-sm text-slate-600">Показатель</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={editForm.indicator_name} onChange={(e) => setEditForm((f) => ({ ...f, indicator_name: e.target.value }))} />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Период</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={editForm.period} onChange={(e) => setEditForm((f) => ({ ...f, period: e.target.value }))} />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Значение</span>
                <input type="number" step="any" className="mt-1 w-full rounded border px-3 py-2" value={editForm.value || ""} onChange={(e) => setEditForm((f) => ({ ...f, value: parseFloat(e.target.value) || 0 }))} />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Прирост % (опц.)</span>
                <input type="number" step="any" className="mt-1 w-full rounded border px-3 py-2" value={editForm.change_pct ?? ""} onChange={(e) => setEditForm((f) => ({ ...f, change_pct: e.target.value === "" ? null : parseFloat(e.target.value) || 0 }))} />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Ед. изм. (опц.)</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={editForm.unit} onChange={(e) => setEditForm((f) => ({ ...f, unit: e.target.value }))} />
              </label>
              <label className="block">
                <span className="text-sm text-slate-600">Источник (опц.)</span>
                <input className="mt-1 w-full rounded border px-3 py-2" value={editForm.source_name} onChange={(e) => setEditForm((f) => ({ ...f, source_name: e.target.value }))} />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button className="rounded border px-4 py-2 text-sm" onClick={() => setEditOpen(false)} disabled={editBusy}>
                Отмена
              </button>
              <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50" onClick={handleEditSave} disabled={editBusy || !editForm.indicator_name.trim() || !editForm.period.trim()}>
                {editBusy ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Import from file */}
      {user?.role === "Admin" ? (
        <div className="mt-4 rounded-lg border-2 border-slate-200 bg-slate-50 p-4">
          <h2 className="text-base font-semibold text-slate-800">Импорт из файла</h2>
          <p className="mt-1 text-sm text-slate-600">
            Excel (.xlsx) — предпочтительно для таблиц (ключевая ставка ЦБ и др.). PDF и скриншоты распознаются через OCR; перед сохранением проверьте все строки.
          </p>
          {parseError ? (
            <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-800">
              {parseError}
              <button type="button" className="ml-2 underline" onClick={() => setParseError(null)}>
                Закрыть
              </button>
            </div>
          ) : null}
          <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
            <input type="file" accept=".pdf,.xlsx,.xlsm,.png,.jpg,.jpeg,.webp,.bmp" className="hidden" onChange={handleParseFile} disabled={parseLoading} />
            <FileUp className="h-4 w-4" />
            {parseLoading ? "Парсинг…" : "Выбрать файл"}
          </label>
        </div>
      ) : null}

      {/* Import preview */}
      {importOpen && parsedRows.length > 0 ? (
        <div className="mt-6 rounded-lg border-2 border-amber-200 bg-amber-50/50 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-800">Редактирование перед сохранением</h2>
            <div className="flex gap-2">
              <input className="rounded border bg-white px-3 py-1.5 text-sm" placeholder="Источник" value={sourceName} onChange={(e) => setSourceName(e.target.value)} />
              <button className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white" onClick={handleSaveImport} disabled={parseLoading}>
                Сохранить в БД
              </button>
              <button className="rounded border bg-white px-3 py-1.5 text-sm" onClick={() => { setImportOpen(false); setParseError(null); }}>
                Отмена
              </button>
            </div>
          </div>
          <div className="mt-3 max-h-[300px] overflow-auto rounded border bg-white">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-slate-50">
                <tr>
                  <th className="px-3 py-2">Показатель</th>
                  <th className="px-3 py-2">Период</th>
                  <th className="px-3 py-2">Значение</th>
                  <th className="px-3 py-2">Прирост %</th>
                  <th className="px-3 py-2">Ед.</th>
                  <th className="w-10"></th>
                </tr>
              </thead>
              <tbody>
                {parsedRows.map((r, idx) => (
                  <tr key={idx} className="border-t">
                    <td className="px-3 py-1.5">
                      <input className="w-full min-w-[140px] rounded border px-2 py-1" value={r.indicator_name} onChange={(e) => updateParsedRow(idx, "indicator_name", e.target.value)} />
                    </td>
                    <td className="px-3 py-1.5">
                      <input className="w-24 rounded border px-2 py-1" value={r.period} onChange={(e) => updateParsedRow(idx, "period", e.target.value)} />
                    </td>
                    <td className="px-3 py-1.5">
                      <input type="number" step="any" className="w-24 rounded border px-2 py-1" value={r.value} onChange={(e) => updateParsedRow(idx, "value", parseFloat(e.target.value) || 0)} />
                    </td>
                    <td className="px-3 py-1.5">
                      <input type="number" step="any" className="w-20 rounded border px-2 py-1" value={r.change_pct ?? ""} onChange={(e) => updateParsedRow(idx, "change_pct", e.target.value === "" ? null : parseFloat(e.target.value) || 0)} placeholder="—" />
                    </td>
                    <td className="px-3 py-1.5">
                      <input className="w-20 rounded border px-2 py-1" value={r.unit ?? ""} onChange={(e) => updateParsedRow(idx, "unit", e.target.value)} placeholder="—" />
                    </td>
                    <td>
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
