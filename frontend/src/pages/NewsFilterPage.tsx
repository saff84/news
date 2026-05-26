import { useEffect, useState } from "react";
import { Filter, Loader2, Save, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

function parseKeywords(text: string): string[] {
  const out: string[] = [];
  for (const line of text.replace(/,/g, "\n").replace(/;/g, "\n").split("\n")) {
    for (const token of line.split(/\s+/)) {
      const t = token.trim().toLowerCase();
      if (t && !out.includes(t)) out.push(t);
    }
  }
  return out;
}

function keywordsToText(list: string[]): string {
  return (list || []).join("\n");
}

export function NewsFilterPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";

  const [loading, setLoading] = useState(true);
  const [saveBusy, setSaveBusy] = useState(false);
  const [cleanupBusy, setCleanupBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);

  const [globalExclude, setGlobalExclude] = useState("");
  const [globalInclude, setGlobalInclude] = useState("");
  const [matchWholeWords, setMatchWholeWords] = useState(false);

  const [previewText, setPreviewText] = useState("");
  const [previewResult, setPreviewResult] = useState<{
    keep: boolean;
    reason: string;
    matched_keywords: string[];
  } | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const c = await api.newsFilter.get(accessToken);
      setGlobalExclude(keywordsToText(c.global_exclude_keywords));
      setGlobalInclude(keywordsToText(c.global_include_keywords));
      setMatchWholeWords(c.match_whole_words);
    } catch (e: unknown) {
      push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Не удалось загрузить" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, [accessToken]);

  const handleSave = async () => {
    if (!accessToken || !isAdmin) return;
    setSaveBusy(true);
    try {
      await api.newsFilter.update(accessToken, {
        global_exclude_keywords: parseKeywords(globalExclude),
        global_include_keywords: parseKeywords(globalInclude),
        match_whole_words: matchWholeWords,
      });
      push({ variant: "success", title: "Сохранено", description: "Глобальные фильтры обновлены" });
      await reload();
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
      <h1 className="text-lg font-semibold">Фильтры новостей</h1>
      <p className="mt-1 text-sm text-slate-600">
        Минус-слова для всех источников плюс локальные фильтры в карточке каждого источника.
      </p>

      <HintBox>
        <div className="font-medium">Как работает</div>
        <ul className="mt-1 list-inside list-disc text-sm">
          <li>
            <b>Глобальные минус-слова</b> — не сохранять новость ни из одного источника, если слово есть в заголовке, тексте или URL.
          </li>
          <li>
            <b>Минус-слова источника</b> — в разделе «Источники» → «Исключить»; суммируются с глобальными.
          </li>
          <li>
            <b>Плюс-слова</b> (глобальные или у источника) — если список не пуст, нужно хотя бы одно совпадение.
          </li>
          <li>Фильтр срабатывает при сборе; для старых записей — «Очистить базу» ниже.</li>
        </ul>
      </HintBox>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">Глобальные ключи</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Минус-слова (для всех источников)</span>
            <textarea
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              rows={6}
              placeholder={"реклама\nвакансия\nпромокод"}
              value={globalExclude}
              onChange={(e) => setGlobalExclude(e.target.value)}
              disabled={!isAdmin}
            />
            <span className="mt-1 block text-xs text-slate-500">По одному на строку, через запятую или пробел.</span>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Плюс-слова (глобально, опционально)</span>
            <textarea
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              rows={6}
              placeholder="жильё&#10;новостройка"
              value={globalInclude}
              onChange={(e) => setGlobalInclude(e.target.value)}
              disabled={!isAdmin}
            />
            <span className="mt-1 block text-xs text-slate-500">
              Если заданы — новость должна содержать хотя бы одно (вместе с плюс-словами источника, если они есть).
            </span>
          </label>
        </div>
        <label className="mt-3 flex items-center gap-2">
          <input
            type="checkbox"
            checked={matchWholeWords}
            onChange={(e) => setMatchWholeWords(e.target.checked)}
            disabled={!isAdmin}
            className="rounded border-slate-300"
          />
          <span className="text-sm text-slate-700">Искать целые слова (не подстроку «ак» внутри «акция»)</span>
        </label>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
            onClick={handleSave}
            disabled={saveBusy || !isAdmin}
          >
            {saveBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Сохранить
          </button>
        </div>
      </div>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">Проверка текста</h2>
        <p className="mt-1 text-xs text-slate-500">Сначала сохраните глобальные ключи, затем вставьте пример заголовка или поста.</p>
        <textarea
          className="mt-2 w-full rounded border px-3 py-2 text-sm"
          rows={4}
          value={previewText}
          onChange={(e) => setPreviewText(e.target.value)}
          placeholder="Заголовок и фрагмент новости…"
        />
        <button
          type="button"
          className="mt-2 inline-flex items-center gap-2 rounded border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
          disabled={previewBusy || !previewText.trim()}
          onClick={async () => {
            if (!accessToken) return;
            setPreviewBusy(true);
            setPreviewResult(null);
            try {
              const r = await api.newsFilter.preview(accessToken, { text: previewText });
              setPreviewResult(r);
            } catch (e: unknown) {
              push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Превью не удалось" });
            } finally {
              setPreviewBusy(false);
            }
          }}
        >
          {previewBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Filter className="h-4 w-4" />}
          Проверить
        </button>
        {previewResult ? (
          <div
            className={`mt-3 rounded border p-3 text-sm ${
              previewResult.keep ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-900"
            }`}
          >
            {previewResult.keep ? "Будет сохранена" : "Будет отброшена"}
            <span className="ml-2 text-xs opacity-80">
              ({previewResult.reason}
              {previewResult.matched_keywords.length ? `: ${previewResult.matched_keywords.join(", ")}` : ""})
            </span>
          </div>
        ) : null}
      </div>

      {isAdmin ? (
        <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-4">
          <h2 className="text-sm font-semibold text-amber-900">Очистка базы</h2>
          <p className="mt-1 text-xs text-amber-800">
            Удаляет уже сохранённые новости, не прошедшие глобальный и локальный фильтр. Сначала сохраните ключи выше.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded border border-amber-400 bg-amber-100 px-3 py-2 text-sm text-amber-900 hover:bg-amber-200 disabled:opacity-50"
              disabled={cleanupBusy}
              onClick={async () => {
                if (!accessToken) return;
                if (!confirm("Подсчитать, сколько новостей будет удалено? (без удаления)")) return;
                setCleanupBusy(true);
                try {
                  const r = await api.newsFilter.cleanup(accessToken, { dry_run: true });
                  push({
                    variant: "success",
                    title: "Пробный подсчёт",
                    description: `Будет удалено: ${r.deleted} из ${r.total_checked}`,
                  });
                } catch (e: unknown) {
                  push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Ошибка" });
                } finally {
                  setCleanupBusy(false);
                }
              }}
            >
              Подсчитать
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded bg-red-700 px-3 py-2 text-sm text-white hover:bg-red-800 disabled:opacity-50"
              disabled={cleanupBusy}
              onClick={async () => {
                if (!accessToken) return;
                if (!confirm("Удалить из БД все новости, не прошедшие фильтр? Действие необратимо.")) return;
                setCleanupBusy(true);
                try {
                  const r = await api.newsFilter.cleanup(accessToken, { dry_run: false });
                  push({
                    variant: "success",
                    title: "Очистка выполнена",
                    description: `Удалено: ${r.deleted} из ${r.total_checked}`,
                  });
                } catch (e: unknown) {
                  push({ variant: "error", title: "Ошибка", description: e instanceof Error ? e.message : "Ошибка" });
                } finally {
                  setCleanupBusy(false);
                }
              }}
            >
              {cleanupBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Очистить всю базу
            </button>
          </div>
        </div>
      ) : null}

      {!isAdmin ? (
        <p className="mt-3 text-xs text-amber-800">Редактирование и очистка — только для Admin.</p>
      ) : null}
    </div>
  );
}
