import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Save, XCircle } from "lucide-react";
import { api, type VkParserStatusOut } from "../lib/api";
import { useAuth } from "../state/auth";

export function VkParserPage() {
  const { accessToken, user } = useAuth();
  const isAdmin = user?.role === "Admin";
  const canTest = user?.role === "Admin" || user?.role === "Analyst";

  const [status, setStatus] = useState<VkParserStatusOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [token, setToken] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [checkBusy, setCheckBusy] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [checkMsg, setCheckMsg] = useState<string | null>(null);
  const [checkErr, setCheckErr] = useState<string | null>(null);

  const [groupId, setGroupId] = useState("");
  const [testBusy, setTestBusy] = useState(false);
  const [testErr, setTestErr] = useState<string | null>(null);
  const [testRes, setTestRes] = useState<{ fetched: number; sample: Array<{ id?: string; text?: string; date?: string; url?: string | null }> } | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const s = await api.vkParser.status(accessToken);
      setStatus(s);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки статуса");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const saveToken = async () => {
    if (!accessToken || !isAdmin) return;
    setSaveBusy(true);
    setSaveErr(null);
    setSaveMsg(null);
    try {
      await api.vkParser.updateConfig(accessToken, { access_token: token || null });
      setSaveMsg("VK токен сохранён в БД.");
      await reload();
    } catch (e: any) {
      setSaveErr(e?.message || "Ошибка сохранения");
    } finally {
      setSaveBusy(false);
    }
  };

  const checkToken = async () => {
    if (!accessToken || !canTest) return;
    if (!token.trim()) {
      setCheckErr("Введите токен для проверки.");
      return;
    }
    setCheckBusy(true);
    setCheckErr(null);
    setCheckMsg(null);
    try {
      const res = await api.vkParser.testToken(accessToken, token.trim());
      if (res.ok) setCheckMsg("Токен валиден для вызова VK API.");
      else setCheckErr(res.error || "Проверка не прошла");
    } catch (e: any) {
      setCheckErr(e?.message || "Ошибка проверки");
    } finally {
      setCheckBusy(false);
    }
  };

  const testFetch = async () => {
    if (!accessToken || !canTest) return;
    if (!groupId.trim()) {
      setTestErr("Введите group id / domain");
      return;
    }
    setTestBusy(true);
    setTestErr(null);
    setTestRes(null);
    try {
      const res = await api.vkParser.testFetch(accessToken, { group_id: groupId.trim(), limit: 5 });
      setTestRes(res);
    } catch (e: any) {
      setTestErr(e?.message || "Ошибка тестового запроса");
    } finally {
      setTestBusy(false);
    }
  };

  const Badge = ({ ok, text }: { ok: boolean; text: string }) => (
    <div className="flex items-center gap-2 text-sm">
      {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-red-600" />}
      <span className={ok ? "text-emerald-700" : "text-red-700"}>{text}</span>
    </div>
  );

  return (
    <div>
      <h1 className="text-lg font-semibold">VK-парсер</h1>
      <p className="mt-1 text-sm text-slate-600">Подключение VK API, проверка токена и тест чтения постов из открытого сообщества.</p>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">1) Как получить токен VK API</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li>Создайте приложение в кабинете VK для разработчиков.</li>
          <li>Получите User/Service токен с доступом к API чтения стены (wall).</li>
          <li>Убедитесь, что сообщество открытое и посты доступны публично.</li>
          <li>В источнике типа <code>VK_GROUP</code> указывайте <code>vk_group_id</code> (public/club/id/domain).</li>
        </ol>
      </div>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">2) Токен VK</h2>
        <p className="mt-1 text-xs text-slate-600">
          Можно хранить токен в БД (эта форма) или в env <code>VK_ACCESS_TOKEN</code>. Если в БД задан токен, он приоритетнее.
        </p>
        <label className="mt-2 block">
          <div className="text-sm text-slate-700">Access token</div>
          <input
            className="mt-1 w-full rounded border px-3 py-2 text-sm"
            type="password"
            placeholder="vk1.a...."
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </label>
        <div className="mt-3 flex items-center gap-2">
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50" onClick={checkToken} disabled={!canTest || checkBusy}>
            Проверить токен
          </button>
          <button className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50" onClick={saveToken} disabled={!isAdmin || saveBusy}>
            <Save className="h-4 w-4" />
            Сохранить токен
          </button>
          {saveMsg ? <span className="text-sm text-emerald-700">{saveMsg}</span> : null}
          {saveErr ? <span className="text-sm text-red-700">{saveErr}</span> : null}
        </div>
        {checkMsg ? <div className="mt-2 text-xs text-emerald-700">{checkMsg}</div> : null}
        {checkErr ? <div className="mt-2 text-xs text-red-700">{checkErr}</div> : null}
      </div>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">3) Статус подключения</h2>
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          <Badge ok={!!status?.token_configured} text={status?.token_configured ? "Токен настроен" : "Токен не настроен"} />
          {status?.token_valid === null ? (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <AlertCircle className="h-4 w-4" />
              Проверка токена не выполнялась
            </div>
          ) : (
            <Badge ok={!!status?.token_valid} text={status?.token_valid ? "Токен валиден" : "Токен невалиден"} />
          )}
        </div>
        <div className="mt-2 text-xs text-slate-600">
          Источник токена: <b>{status?.token_source || "—"}</b>; API: <code>{status?.api_base || "—"}</code>; версия: <code>{status?.api_version || "—"}</code>
        </div>
        {status?.verify_error ? <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{status.verify_error}</div> : null}
      </div>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">4) Тест чтения из группы</h2>
        <p className="mt-1 text-xs text-slate-600">
          Тест вызова <code>wall.get</code>. Примеры ID: <code>public123456</code>, <code>club123456</code>, <code>123456</code>, <code>domain</code>.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <input className="min-w-[280px] rounded border px-3 py-2 text-sm" placeholder="group id / domain" value={groupId} onChange={(e) => setGroupId(e.target.value)} />
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50" onClick={testFetch} disabled={!canTest || testBusy}>
            Тестовый fetch
          </button>
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" onClick={reload} disabled={loading}>
            Обновить статус
          </button>
        </div>
        {testErr ? <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{testErr}</div> : null}
        {testRes ? (
          <div className="mt-2 rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900">
            Получено постов: <b>{testRes.fetched}</b>
            {testRes.sample.length > 0 ? (
              <ul className="mt-1 list-disc pl-4">
                {testRes.sample.map((m, i) => (
                  <li key={`${m.id || "id"}-${i}`}>
                    <code>{m.id || "—"}</code> · {m.date || "—"} · {(m.text || "").slice(0, 90)}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </div>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}
    </div>
  );
}
