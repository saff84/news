import { useEffect, useMemo, useState } from "react";
import { api, type DeveloperOut, type RegionOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HelpText, HintBox } from "../components/Field";

type DeveloperForm = {
  name: string;
  aliases: string;
  tags: string;
  region_ids: string[];
  is_active: boolean;
};

function parseLines(s: string): string[] {
  return s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}

function toForm(d?: DeveloperOut): DeveloperForm {
  return {
    name: d?.name ?? "",
    aliases: (d?.aliases ?? []).join("\n"),
    tags: (d?.tags ?? []).join("\n"),
    region_ids: d?.region_ids ?? [],
    is_active: d?.is_active ?? true,
  };
}

export function DevelopersPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";
  const canWrite = isAdmin;

  const [q, setQ] = useState("");
  const [items, setItems] = useState<DeveloperOut[]>([]);
  const [regions, setRegions] = useState<RegionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DeveloperOut | null>(null);
  const [form, setForm] = useState<DeveloperForm>(() => toForm());

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [d, r] = await Promise.all([api.developers.list(accessToken, q || undefined), api.regions.list(accessToken)]);
      setItems(d.items);
      setRegions(r.items);
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

  const regionById = useMemo(() => new Map(regions.map((r) => [r.id, r.name])), [regions]);

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Застройщики</h1>
          <p className="mt-1 text-sm text-slate-600">
            Отдельный справочник от конкурентов. Используется для привязки источников, тегов в новостях и раздела «Застройщики» в отчётах.
          </p>
          <HintBox>
            <div className="font-medium">Подсказка</div>
            <div className="mt-1">Добавьте алиасы брендов и юрлиц — так выше точность авто-тегирования и качество саммари.</div>
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
            Добавить застройщика
          </button>
        ) : null}
      </div>

      <div className="mt-4 flex gap-2">
        <input className="w-full rounded border bg-white px-3 py-2 text-sm" placeholder="Поиск по имени…" value={q} onChange={(e) => setQ(e.target.value)} />
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
              <th className="px-3 py-2">Алиасы</th>
              <th className="px-3 py-2">Теги</th>
              <th className="px-3 py-2">Регионы</th>
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
              items.map((c) => (
                <tr key={c.id} className="border-t">
                  <td className="px-3 py-2 font-medium">{c.name}</td>
                  <td className="px-3 py-2">{c.is_active ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">{c.aliases.length}</td>
                  <td className="px-3 py-2">{c.tags.length}</td>
                  <td className="px-3 py-2">{c.region_ids.map((id) => regionById.get(id) || id).join(", ") || "—"}</td>
                  <td className="px-3 py-2 text-right">
                    {canWrite ? (
                      <div className="flex justify-end gap-2">
                        <button
                          className="rounded border px-2 py-1 text-xs hover:bg-slate-50"
                          onClick={() => {
                            setEditing(c);
                            setForm(toForm(c));
                            setModalOpen(true);
                          }}
                        >
                          Редактировать
                        </button>
                        <button
                          className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                          onClick={async () => {
                            if (!accessToken) return;
                            if (!confirm(`Удалить застройщика "${c.name}"?`)) return;
                            try {
                              await api.developers.delete(accessToken, c.id);
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
          <div className="max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-lg bg-white shadow-lg">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-4 py-3">
              <div className="text-sm font-semibold">{editing ? "Редактировать застройщика" : "Новый застройщик"}</div>
              <button className="rounded px-2 py-1 text-sm hover:bg-slate-50" onClick={() => setModalOpen(false)}>
                ✕
              </button>
            </div>

            <div className="max-h-[calc(90vh-120px)] overflow-y-auto px-4 py-4">
              <div className="grid gap-3">
                <label className="block">
                  <div className="text-sm text-slate-700">Название</div>
                  <input className="mt-1 w-full rounded border px-3 py-2 text-sm" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                  <HelpText>Используется в отчётах и фильтрах.</HelpText>
                </label>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="block">
                    <div className="text-sm text-slate-700">Алиасы (по 1 в строке)</div>
                    <textarea className="mt-1 h-36 w-full rounded border px-3 py-2 text-sm" value={form.aliases} onChange={(e) => setForm((f) => ({ ...f, aliases: e.target.value }))} />
                    <HelpText>Варианты написания для поиска в тексте новостей.</HelpText>
                  </label>
                  <label className="block">
                    <div className="text-sm text-slate-700">Теги (по 1 в строке)</div>
                    <textarea className="mt-1 h-36 w-full rounded border px-3 py-2 text-sm" value={form.tags} onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))} />
                    <HelpText>Произвольные метки для группировки.</HelpText>
                  </label>
                </div>

                <div>
                  <div className="text-sm text-slate-700">Регионы присутствия</div>
                  <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                    {regions.map((r) => (
                      <label key={r.id} className="inline-flex items-center gap-2 rounded border bg-white px-2 py-1 text-sm">
                        <input
                          type="checkbox"
                          checked={form.region_ids.includes(r.id)}
                          onChange={(e) => {
                            setForm((f) => {
                              const set = new Set(f.region_ids);
                              if (e.target.checked) set.add(r.id);
                              else set.delete(r.id);
                              return { ...f, region_ids: Array.from(set) };
                            });
                          }}
                        />
                        <span>{r.name}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <label className="inline-flex items-center gap-2">
                  <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
                  <span className="text-sm text-slate-700">Активен</span>
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
                      aliases: parseLines(form.aliases),
                      tags: parseLines(form.tags),
                      region_ids: form.region_ids,
                      is_active: form.is_active,
                    };
                    if (editing) await api.developers.update(accessToken, editing.id, payload);
                    else await api.developers.create(accessToken, payload);
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
