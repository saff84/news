import { useEffect, useState } from "react";
import { api, type ParsingTemplateOut } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HelpText, HintBox, InstructionBox } from "../components/Field";

type TemplateForm = {
  name: string;
  version: number;
  is_active: boolean;
  template_json_text: string;
};

function prettyJson(v: any) {
  return JSON.stringify(v ?? {}, null, 2);
}

function toForm(t?: ParsingTemplateOut): TemplateForm {
  return {
    name: t?.name ?? "",
    version: t?.version ?? 1,
    is_active: t?.is_active ?? true,
    template_json_text: prettyJson(t?.template_json ?? {}),
  };
}

export function ParsingTemplatesPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";
  const canWrite = isAdmin;

  const [q, setQ] = useState("");
  const [items, setItems] = useState<ParsingTemplateOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ParsingTemplateOut | null>(null);
  const [form, setForm] = useState<TemplateForm>(() => toForm());

  const [testUrl, setTestUrl] = useState("");
  const [testResult, setTestResult] = useState<any>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.parsingTemplates.list(accessToken, q || undefined);
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

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Шаблоны парсинга (HTML)</h1>
          <p className="mt-1 text-sm text-slate-600">
            Шаблон — JSON с CSS-селекторами для <b>детальной страницы</b> статьи и опционально для <b>списка ссылок</b>. Его привязывают к источнику типа «HTML: список→деталь» или «только деталь».
          </p>
          <HintBox>
            Минимальный рабочий тест: блок <code className="rounded bg-white px-1">detail</code> (поля <code className="rounded bg-white px-1">title</code>, <code className="rounded bg-white px-1">date</code>,{" "}
            <code className="rounded bg-white px-1">body</code>) и <code className="rounded bg-white px-1">cleanup.remove_css</code> — чтобы убрать меню и рекламу до извлечения текста.
          </HintBox>
          <InstructionBox title="Как пользоваться (пошагово)">
            <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-700">
              <li>
                Откройте <b>одну типичную статью</b> на целевом сайте в браузере и скопируйте её URL — его используют в «Тест шаблона».
              </li>
              <li>
                В DevTools посмотрите, где лежат заголовок (<code>h1</code>), дата (<code>time</code> с атрибутом <code>datetime</code>), основной текст (<code>article</code>, <code>.content</code> и т.д.).
              </li>
              <li>
                Соберите JSON: для каждого поля укажите <code>css</code> (селектор) и при необходимости <code>attr</code> (например <code>datetime</code> для даты вместо видимого текста).
              </li>
              <li>
                Нажмите <b>Протестировать</b> — в ответе должны быть непустые <code>title</code>, <code>body_text</code> и по возможности <code>published_at</code>.
              </li>
              <li>
                Для источника «список→деталь» добавьте блок <code>list</code> (см. ниже), сохраните шаблон и выберите его в карточке источника на странице «Источники».
              </li>
            </ol>
          </InstructionBox>
          <InstructionBox title="Справочник полей JSON">
            <div className="space-y-3 text-sm text-slate-700">
              <div>
                <div className="font-medium text-slate-800">detail.* — одна статья (обязательно для любого HTML-источника с шаблоном)</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  <li>
                    <code>detail.title</code>, <code>detail.date</code>, <code>detail.author</code>, <code>detail.body</code> — объекты вида{" "}
                    <code>{`{ "css": "селектор", "attr": "опционально атрибут" }`}</code>. Если <code>attr</code> задан, берётся значение атрибута элемента, иначе — видимый текст.
                  </li>
                  <li>
                    <code>detail.body</code> — контейнер основного текста; из него строится вступление/полный текст новости. Если текста мало, бэкенд может подключить readability как запасной вариант.
                  </li>
                </ul>
              </div>
              <div>
                <div className="font-medium text-slate-800">cleanup — подготовка DOM</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  <li>
                    <code>cleanup.remove_css</code> — массив селекторов узлов, которые удаляются <b>до</b> чтения полей (шапка, сайдбар, блок «поделиться», подписка).
                  </li>
                </ul>
              </div>
              <div>
                <div className="font-medium text-slate-800">list — только для режима «HTML: список → деталь»</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  <li>
                    <code>list.item_links_css</code> — селектор элементов <b>ссылок</b> на статьи (часто <code>article a</code>, <code>.news-list a</code>). По найденным <code>href</code> открываются детальные страницы и к ним применяется <code>detail</code>.
                  </li>
                  <li>
                    <code>list.next_page_css</code> — опционально: селектор ссылки «следующая страница» для листинга.
                  </li>
                  <li>
                    <code>list.max_pages</code> — сколько страниц списка обойти (по умолчанию 1).
                  </li>
                </ul>
              </div>
              <div>
                <div className="font-medium text-slate-800">Прочее</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  <li>
                    <code>min_fulltext_length</code> — если вытащенный <code>body</code> короче этого числа символов, пробуется запасной режим readability.
                  </li>
                </ul>
              </div>
            </div>
          </InstructionBox>
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
            Добавить шаблон
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
        <table className="min-w-[700px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">Название</th>
              <th className="px-3 py-2">Версия</th>
              <th className="px-3 py-2">Активен</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={4}>
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td className="px-3 py-3 text-slate-600" colSpan={4}>
                  Пусто
                </td>
              </tr>
            ) : (
              items.map((t) => (
                <tr key={t.id} className="border-t">
                  <td className="px-3 py-2 font-medium">{t.name}</td>
                  <td className="px-3 py-2">{t.version}</td>
                  <td className="px-3 py-2">{t.is_active ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2 text-right">
                    {canWrite ? (
                      <div className="flex justify-end gap-2">
                        <button
                          className="rounded border px-2 py-1 text-xs hover:bg-slate-50"
                          onClick={() => {
                            setEditing(t);
                            setForm(toForm(t));
                            setModalOpen(true);
                          }}
                        >
                          Редактировать
                        </button>
                        <button
                          className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                          onClick={async () => {
                            if (!accessToken) return;
                            if (!confirm(`Удалить шаблон "${t.name}" v${t.version}?`)) return;
                            try {
                              await api.parsingTemplates.delete(accessToken, t.id);
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

      <div className="mt-6 rounded border bg-white p-4">
        <div className="text-sm font-semibold">Тест шаблона (dry-run)</div>
        <HelpText>Работает только для Admin. Шаблон передаётся как JSON прямо из поля ниже.</HelpText>
        <div className="mt-3 grid gap-2">
          <input className="w-full rounded border px-3 py-2 text-sm" placeholder="URL статьи (detail page)..." value={testUrl} onChange={(e) => setTestUrl(e.target.value)} />
          <textarea
            className="h-56 w-full rounded border px-3 py-2 font-mono text-xs"
            value={form.template_json_text}
            onChange={(e) => setForm((f) => ({ ...f, template_json_text: e.target.value }))}
          />
          <div className="flex gap-2">
            <button
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
              disabled={!accessToken || !isAdmin}
              onClick={async () => {
                if (!accessToken) return;
                setTestError(null);
                setTestResult(null);
                try {
                  const json = JSON.parse(form.template_json_text || "{}");
                  const res = await api.templates.test(accessToken, testUrl, json);
                  setTestResult(res);
                } catch (e: any) {
                  setTestError(e?.message || "Ошибка теста");
                }
              }}
            >
              Протестировать
            </button>
            <button className="rounded border px-3 py-2 text-sm hover:bg-slate-50" onClick={() => setForm((f) => ({ ...f, template_json_text: prettyJson({ detail: { title: { css: "h1" }, date: { css: "time", attr: "datetime" }, body: { css: "article" } }, cleanup: { remove_css: [".share", ".ads"] } }) }))}>
              Вставить пример
            </button>
          </div>
          {testError ? <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{testError}</div> : null}
          {testResult ? <pre className="overflow-auto rounded border bg-slate-50 p-2 text-xs">{JSON.stringify(testResult, null, 2)}</pre> : null}
        </div>
      </div>

      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-lg bg-white shadow-lg">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-4 py-3">
              <div className="text-sm font-semibold">{editing ? "Редактировать шаблон" : "Новый шаблон"}</div>
              <button className="rounded px-2 py-1 text-sm hover:bg-slate-50" onClick={() => setModalOpen(false)}>
                ✕
              </button>
            </div>

            <div className="max-h-[calc(90vh-120px)] overflow-y-auto px-4 py-4">
              <div className="grid gap-3">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <label className="block md:col-span-2">
                  <div className="text-sm text-slate-700">Название</div>
                  <input className="mt-1 w-full rounded border px-3 py-2 text-sm" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                  <HelpText>Человеко‑читаемое имя шаблона (обычно = сайт/раздел). Уникальность обеспечивается парой name+version.</HelpText>
                </label>
                <label className="block">
                  <div className="text-sm text-slate-700">Версия</div>
                  <input className="mt-1 w-full rounded border px-3 py-2 text-sm" type="number" value={form.version} onChange={(e) => setForm((f) => ({ ...f, version: Number(e.target.value || 1) }))} />
                  <HelpText>Увеличивайте версию при изменениях селекторов, чтобы сохранять историю.</HelpText>
                </label>
              </div>

              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
                <span className="text-sm text-slate-700">Активен</span>
                <span className="text-xs text-slate-500">Неактивные шаблоны не предлагаются при настройке источников.</span>
              </label>

              <label className="block">
                <div className="text-sm text-slate-700">Template JSON</div>
                <textarea className="mt-1 h-80 w-full rounded border px-3 py-2 font-mono text-xs" value={form.template_json_text} onChange={(e) => setForm((f) => ({ ...f, template_json_text: e.target.value }))} />
                <HelpText>JSON с правилами извлечения. Для быстрого старта используйте кнопку “Вставить пример” в блоке теста.</HelpText>
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
                    const template_json = JSON.parse(form.template_json_text || "{}");
                    const payload = { name: form.name, version: form.version, is_active: form.is_active, template_json };
                    if (editing) await api.parsingTemplates.update(accessToken, editing.id, payload);
                    else await api.parsingTemplates.create(accessToken, payload);
                    setModalOpen(false);
                    await reload();
                  } catch (e: any) {
                    push({ variant: "error", title: "Не удалось сохранить", description: e?.message || "Ошибка сохранения (проверьте JSON)" });
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

