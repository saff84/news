import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Save, XCircle } from "lucide-react";
import { api, type MaxParserStatusOut } from "../lib/api";
import { useAuth } from "../state/auth";

export function MaxParserPage() {
  const { accessToken, user } = useAuth();
  const isAdmin = user?.role === "Admin";
  const canTest = user?.role === "Admin" || user?.role === "Analyst";

  const [status, setStatus] = useState<MaxParserStatusOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [botToken, setBotToken] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [checkBusy, setCheckBusy] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [checkMsg, setCheckMsg] = useState<string | null>(null);
  const [checkErr, setCheckErr] = useState<string | null>(null);

  const [channelId, setChannelId] = useState("");
  const [testBusy, setTestBusy] = useState(false);
  const [testErr, setTestErr] = useState<string | null>(null);
  const [testRes, setTestRes] = useState<{ fetched: number; sample: Array<{ id?: string; text?: string; date?: string }> } | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const s = await api.maxParser.status(accessToken);
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
      await api.maxParser.updateConfig(accessToken, { bot_token: botToken || null });
      setSaveMsg("Токен сохранён в БД.");
      await reload();
    } catch (e: any) {
      setSaveErr(e?.message || "Ошибка сохранения");
    } finally {
      setSaveBusy(false);
    }
  };

  const checkToken = async () => {
    if (!accessToken || !canTest) return;
    if (!botToken.trim()) {
      setCheckErr("Введите токен для проверки.");
      return;
    }
    setCheckBusy(true);
    setCheckErr(null);
    setCheckMsg(null);
    try {
      const res = await api.maxParser.testBot(accessToken, botToken.trim());
      if (res.ok) {
        const uname = res.bot_info?.username || res.bot_info?.name || "бот найден";
        setCheckMsg(`Токен валиден: ${uname}`);
      } else {
        setCheckErr(res.error || "Проверка не прошла");
      }
    } catch (e: any) {
      setCheckErr(e?.message || "Ошибка проверки");
    } finally {
      setCheckBusy(false);
    }
  };

  const testFetch = async () => {
    if (!accessToken || !canTest) return;
    if (!channelId.trim()) {
      setTestErr("Введите channel/chat id");
      return;
    }
    setTestBusy(true);
    setTestErr(null);
    setTestRes(null);
    try {
      const res = await api.maxParser.testFetch(accessToken, { channel_id: channelId.trim(), limit: 5 });
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
      <h1 className="text-lg font-semibold">MAX-парсер</h1>
      <p className="mt-1 text-sm text-slate-600">
        Подключение MAX Bot API, проверка токена и тест чтения сообщений из открытого канала/чата.
      </p>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">1) Как создать бота и получить токен (подробно)</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li>
            Откройте портал разработчика MAX:{" "}
            <a href="https://dev.max.ru/docs-api" target="_blank" rel="noreferrer" className="underline">
              dev.max.ru/docs-api
            </a>.
          </li>
          <li>В кабинете разработчика создайте приложение/бота (раздел подключения приложения).</li>
          <li>Скопируйте API token бота (используется в заголовке <code>Authorization</code>).</li>
          <li>Добавьте бота в нужный открытый канал/чат и дайте права на чтение сообщений.</li>
          <li>
            Уточните ID канала/чата (его нужно указать как <code>max_channel_id</code> в источнике <code>MAX_CHANNEL</code>).
          </li>
          <li>
            Для production используйте HTTPS webhook; для локальной диагностики можно начинать с ручных запросов/long polling
            (согласно документации MAX).
          </li>
        </ol>
        <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          Рекомендация по лимитам из документации MAX: не превышайте ~30 rps к <code>platform-api.max.ru</code>.
        </div>
      </div>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">2) Токен MAX</h2>
        <p className="mt-1 text-xs text-slate-600">
          Можно хранить токен в БД (эта форма) или в env <code>MAX_BOT_TOKEN</code>. Если в БД задан токен, он приоритетнее.
        </p>
        <label className="mt-2 block">
          <div className="text-sm text-slate-700">Bot token</div>
          <input
            className="mt-1 w-full rounded border px-3 py-2 text-sm"
            type="password"
            placeholder="max_..."
            value={botToken}
            onChange={(e) => setBotToken(e.target.value)}
          />
        </label>
        <div className="mt-3 flex items-center gap-2">
          <button
            className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
            onClick={checkToken}
            disabled={!canTest || checkBusy}
          >
            Проверить токен
          </button>
          <button
            className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
            onClick={saveToken}
            disabled={!isAdmin || saveBusy}
          >
            <Save className="h-4 w-4" />
            Сохранить токен
          </button>
          {saveMsg ? <span className="text-sm text-emerald-700">{saveMsg}</span> : null}
          {saveErr ? <span className="text-sm text-red-700">{saveErr}</span> : null}
        </div>
        {checkMsg ? <div className="mt-2 text-xs text-emerald-700">{checkMsg}</div> : null}
        {checkErr ? <div className="mt-2 text-xs text-red-700">{checkErr}</div> : null}
        {!isAdmin ? (
          <div className="mt-2 text-xs text-amber-700">Сохранять токен может только роль Admin.</div>
        ) : null}
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
            <Badge ok={!!status?.token_valid} text={status?.token_valid ? "Токен валиден (/bots OK)" : "Токен невалиден"} />
          )}
        </div>
        <div className="mt-2 text-xs text-slate-600">
          Источник токена: <b>{status?.token_source || "—"}</b>; API base: <code>{status?.api_base || "—"}</code>
        </div>
        {status?.verify_error ? (
          <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{status.verify_error}</div>
        ) : null}
      </div>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">4) Тест чтения из канала</h2>
        <p className="mt-1 text-xs text-slate-600">
          Проверка вызова <code>GET /messages</code> с параметром <code>chat_id</code>. Убедитесь, что бот добавлен в канал/чат.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            className="min-w-[280px] rounded border px-3 py-2 text-sm"
            placeholder="channel/chat id"
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
          />
          <button
            className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
            onClick={testFetch}
            disabled={!canTest || testBusy}
          >
            Тестовый fetch
          </button>
          <button className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50" onClick={reload} disabled={loading}>
            Обновить статус
          </button>
        </div>
        {!canTest ? <div className="mt-2 text-xs text-amber-700">Тест доступен ролям Admin и Analyst.</div> : null}
        {testErr ? <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{testErr}</div> : null}
        {testRes ? (
          <div className="mt-2 rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900">
            Получено сообщений: <b>{testRes.fetched}</b>
            {testRes.sample.length > 0 ? (
              <ul className="mt-1 list-disc pl-4">
                {testRes.sample.map((m, i) => (
                  <li key={`${m.id || "id"}-${i}`}>
                    <code>{m.id || "—"}</code> · {m.date || "—"} · {(m.text || "").slice(0, 100)}
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
