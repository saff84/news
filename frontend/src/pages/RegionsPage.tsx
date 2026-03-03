import { useEffect, useMemo, useState } from "react";
import { api, type RegionOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HelpText, HintBox } from "../components/Field";

type RegionForm = {
  name: string;
  federal_subjects: string;
  keywords: string;
  geographic_aliases: string;
  is_active: boolean;
};

function parseList(s: string): string[] {
  return s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}

function toForm(r?: RegionOut): RegionForm {
  return {
    name: r?.name ?? "",
    federal_subjects: (r?.federal_subjects ?? []).join("\n"),
    keywords: (r?.keywords ?? []).join("\n"),
    geographic_aliases: (r?.geographic_aliases ?? []).join("\n"),
    is_active: r?.is_active ?? true,
  };
}

export function RegionsPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<RegionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = user?.role === "Admin";

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<RegionOut | null>(null);
  const [form, setForm] = useState<RegionForm>(() => toForm());

  const canWrite = isAdmin;

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.regions.list(accessToken, q || undefined);
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
  }, []);

  const totalActive = useMemo(() => items.filter((x) => x.is_active).length, [items]);

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Регионы (дивизионы)</h1>
          <p className="mt-1 text-sm text-slate-600">
            Всего: {items.length} (активных: {totalActive})
          </p>
          <HintBox>
            Регионы используются для маршрутизации новостей по дивизионам: источники могут быть помечены регионом, а сами новости — автоматически тегироваться по словарям и гео-алиасам.
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
            Добавить регион
          </button>
        ) : null}
      </div>

      <div className="mt-4 flex gap-2">
        <input
          className="w-full rounded border bg-white px-3 py-2 text-sm"
          placeholder="Поиск по имени…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" onClick={reload} disabled={loading}>
          Найти
        </button>
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 overflow-x-auto rounded border bg-white">
        <table className="min-w-[900px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Название</th>
              <th className="px-3 py-2">Активен</th>
              <th className="px-3 py-2">Субъекты</th>
              <th className="px-3 py-2">Ключевые слова</th>
              <th className="px-3 py-2">Алиасы</th>
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
              items.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="px-3 py-2 font-medium">{r.name}</td>
                  <td className="px-3 py-2">{r.is_active ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">{r.federal_subjects.length}</td>
                  <td className="px-3 py-2">{r.keywords.length}</td>
                  <td className="px-3 py-2">{r.geographic_aliases.length}</td>
                  <td className="px-3 py-2 text-right">
                    {canWrite ? (
                      <div className="flex justify-end gap-2">
                        <button
                          className="rounded border px-2 py-1 text-xs hover:bg-slate-50"
                          onClick={() => {
                            setEditing(r);
                            setForm(toForm(r));
                            setModalOpen(true);
                          }}
                        >
                          Редактировать
                        </button>
                        <button
                          className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                          onClick={async () => {
                            if (!accessToken) return;
                            if (!confirm(`Удалить регион "${r.name}"?`)) return;
                            try {
                              await api.regions.delete(accessToken, r.id);
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
          <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-lg bg-white shadow-lg">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-4 py-3">
              <div className="text-sm font-semibold">{editing ? "Редактировать регион" : "Новый регион"}</div>
              <button className="rounded px-2 py-1 text-sm hover:bg-slate-50" onClick={() => setModalOpen(false)}>
                ✕
              </button>
            </div>

            <div className="max-h-[calc(90vh-120px)] overflow-y-auto px-4 py-4">
              <div className="grid gap-3">
              <label className="block">
                <div className="text-sm text-slate-700">Название</div>
                <input
                  className="mt-1 w-full rounded border px-3 py-2 text-sm"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
                <HelpText>Название дивизиона/региона, например: “Северо‑Запад”, “Урал”. Должно быть уникальным.</HelpText>
              </label>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <label className="block">
                  <div className="text-sm text-slate-700">Федеральные субъекты (по 1 в строке)</div>
                  <textarea
                    className="mt-1 h-40 w-full rounded border px-3 py-2 text-sm"
                    value={form.federal_subjects}
                    onChange={(e) => setForm((f) => ({ ...f, federal_subjects: e.target.value }))}
                  />
                  <HelpText>
                    Список субъектов РФ, входящих в регион (для словарной привязки новостей). Пример: “Санкт‑Петербург”, “Ленинградская область”.
                  </HelpText>
                </label>
                <label className="block">
                  <div className="text-sm text-slate-700">Ключевые слова (по 1 в строке)</div>
                  <textarea
                    className="mt-1 h-40 w-full rounded border px-3 py-2 text-sm"
                    value={form.keywords}
                    onChange={(e) => setForm((f) => ({ ...f, keywords: e.target.value }))}
                  />
                  <HelpText>
                    Дополнительные слова/фразы, по которым новости будут относиться к региону (например: названия городов, агломераций, проекты).
                  </HelpText>
                </label>
                <label className="block">
                  <div className="text-sm text-slate-700">Гео-алиасы (по 1 в строке)</div>
                  <textarea
                    className="mt-1 h-40 w-full rounded border px-3 py-2 text-sm"
                    value={form.geographic_aliases}
                    onChange={(e) => setForm((f) => ({ ...f, geographic_aliases: e.target.value }))}
                  />
                  <HelpText>
                    Варианты написания/сокращения географических названий (например: “СПб”, “Питер”, “С‑Пб”), чтобы уменьшить пропуски при матчинге.
                  </HelpText>
                </label>
              </div>

              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                />
                <span className="text-sm text-slate-700">Активен</span>
                <span className="text-xs text-slate-500">Неактивные регионы не используются в автоматической маршрутизации.</span>
              </label>
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
                    const payload = {
                      name: form.name,
                      federal_subjects: parseList(form.federal_subjects),
                      keywords: parseList(form.keywords),
                      geographic_aliases: parseList(form.geographic_aliases),
                      is_active: form.is_active,
                    };
                    if (editing) await api.regions.update(accessToken, editing.id, payload);
                    else await api.regions.create(accessToken, payload);
                    setModalOpen(false);
                    await reload();
                  } catch (e: any) {
                    push({ variant: "error", title: "Не удалось сохранить", description: e?.message || "Ошибка сохранения" });
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

