import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api } from "../lib/api";
import { useAuth } from "../state/auth";
import { CheckCircle2, XCircle, AlertCircle, Save, QrCode } from "lucide-react";

type Status = {
  credentials_configured: boolean;
  session_string_used: boolean;
  session_dir: string;
  session_file_exists: boolean;
  session_authorized: boolean | null;
  verify_error?: string | null;
  config_source?: string;
};

export function TelegramParserPage() {
  const { accessToken, user } = useAuth();
  const isAdmin = user?.role === "Admin";
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({ api_id: "", api_hash: "", session_string: "" });
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [qrState, setQrState] = useState<{
    qrDataUrl: string | null;
    pollId: string | null;
    status: "idle" | "pending" | "done" | "error" | "timeout" | "2fa_required";
    sessionString: string | null;
    error: string | null;
  }>({ qrDataUrl: null, pollId: null, status: "idle", sessionString: null, error: null });
  const [qr2faPassword, setQr2faPassword] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const s = await api.telegramParser.status(accessToken);
      setStatus(s);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки статуса");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, [accessToken]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleGenerateQr = useCallback(async () => {
    if (!accessToken || !isAdmin) return;
    const apiId = parseInt(form.api_id, 10);
    const apiHash = form.api_hash.trim();
    if (!apiId || !apiHash) return;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setQrState({ qrDataUrl: null, pollId: null, status: "pending", sessionString: null, error: null });
    try {
      const res = await api.telegramParser.qrStart(accessToken, apiId, apiHash);
      if (res.session_string) {
        setForm((f) => ({ ...f, session_string: res.session_string! }));
        setQrState({ qrDataUrl: null, pollId: null, status: "done", sessionString: res.session_string, error: null });
        return;
      }
      if (!res.qr_url) {
        setQrState((s) => ({ ...s, status: "error", error: "Не получен QR URL" }));
        return;
      }
      const qrDataUrl = await QRCode.toDataURL(res.qr_url, { width: 256, margin: 2 });
      setQrState({ qrDataUrl, pollId: res.poll_id, status: "pending", sessionString: null, error: null });
      const doPoll = async () => {
        if (!accessToken) return;
        try {
          const poll = await api.telegramParser.qrPoll(accessToken, res.poll_id);
          if (poll.status === "done" && poll.session_string) {
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setForm((f) => ({ ...f, session_string: poll.session_string! }));
            setQrState((s) => ({ ...s, status: "done", sessionString: poll.session_string!, qrDataUrl: null }));
          } else if (poll.status === "2fa_required") {
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setQrState((s) => ({ ...s, status: "2fa_required", qrDataUrl: null }));
          } else if (poll.status === "error" || poll.status === "timeout") {
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setQrState((s) => ({ ...s, status: poll.status as "error" | "timeout", error: poll.error || "Ошибка" }));
          }
        } catch {
          // ignore poll errors
        }
      };
      doPoll();
      pollRef.current = setInterval(doPoll, 1000);
    } catch (e: unknown) {
      setQrState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : "Ошибка" }));
    }
  }, [accessToken, isAdmin, form.api_id, form.api_hash]);

  const handleQr2faSubmit = useCallback(async () => {
    if (!accessToken || !qrState.pollId || !qr2faPassword.trim()) return;
    try {
      const res = await api.telegramParser.qr2fa(accessToken, qrState.pollId, qr2faPassword);
      if (res.status === "done" && res.session_string) {
        setForm((f) => ({ ...f, session_string: res.session_string! }));
        setQrState({ qrDataUrl: null, pollId: null, status: "done", sessionString: res.session_string, error: null });
        setQr2faPassword("");
      } else if (res.status === "error") {
        setQrState((s) => ({ ...s, status: "error", error: res.error || "Неверный пароль" }));
      }
    } catch (e: unknown) {
      setQrState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : "Ошибка" }));
    }
  }, [accessToken, qrState.pollId, qr2faPassword]);

  const handleSave = async () => {
    if (!accessToken || !isAdmin) return;
    setSaveBusy(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const payload: { api_id?: number; api_hash?: string; session_string?: string } = {};
      if (form.api_id) payload.api_id = parseInt(form.api_id, 10);
      if (form.api_hash) payload.api_hash = form.api_hash;
      if (form.session_string) payload.session_string = form.session_string;
      await api.telegramParser.updateConfig(accessToken, payload);
      setSaveSuccess(true);
      reload();
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setSaveBusy(false);
    }
  };

  const StatusBadge = ({ ok, label }: { ok: boolean; label: string }) => (
    <div className="flex items-center gap-2">
      {ok ? (
        <CheckCircle2 className="h-5 w-5 text-emerald-600" />
      ) : (
        <XCircle className="h-5 w-5 text-red-600" />
      )}
      <span className={ok ? "text-emerald-700" : "text-red-700"}>{label}</span>
    </div>
  );

  return (
    <div>
      <h1 className="text-lg font-semibold">Telegram-парсер</h1>
      <p className="mt-1 text-sm text-slate-600">
        Настройка бота для парсинга публичных Telegram-каналов, добавленных в разделе «Источники».
      </p>

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">Учётные данные</h2>
          <p className="mt-1 text-xs text-slate-600">
            API ID и API Hash — с <a href="https://my.telegram.org" target="_blank" rel="noreferrer" className="underline">my.telegram.org</a>. Введите их, нажмите «Сгенерировать QR», отсканируйте QR в Telegram.
          </p>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="block">
              <div className="text-sm text-slate-700">API ID</div>
              <input
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
                type="number"
                placeholder="12345678"
                value={form.api_id}
                onChange={(e) => setForm((f) => ({ ...f, api_id: e.target.value }))}
              />
            </label>
            <label className="block">
              <div className="text-sm text-slate-700">API Hash</div>
              <input
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
                type="password"
                placeholder="••••••••"
                value={form.api_hash}
                onChange={(e) => setForm((f) => ({ ...f, api_hash: e.target.value }))}
              />
            </label>
          </div>
          <label className="mt-3 block">
            <div className="text-sm text-slate-700">Session string</div>
            <textarea
              className="mt-1 w-full rounded border px-3 py-2 text-sm font-mono"
              rows={3}
              placeholder="1BQAN..."
              value={form.session_string}
              onChange={(e) => setForm((f) => ({ ...f, session_string: e.target.value }))}
            />
          </label>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
              onClick={handleSave}
              disabled={saveBusy || !isAdmin}
            >
              <Save className="h-4 w-4" />
              Сохранить
            </button>
            {form.api_id && form.api_hash ? (
              <button
                className="inline-flex items-center gap-2 rounded border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                onClick={handleGenerateQr}
                disabled={!isAdmin || qrState.status === "pending"}
              >
                <QrCode className="h-4 w-4" />
                Сгенерировать QR
              </button>
            ) : null}
            {saveSuccess ? <span className="text-sm text-emerald-600">Сохранено</span> : null}
          </div>
          {qrState.status === "pending" && !qrState.qrDataUrl ? (
            <div className="mt-3 rounded border bg-slate-50 p-4 text-sm text-slate-600">Генерация QR…</div>
          ) : null}
          {qrState.status === "pending" && qrState.qrDataUrl ? (
            <div className="mt-3 rounded border bg-slate-50 p-4">
              <div className="text-sm font-medium text-slate-700">Отсканируйте QR в Telegram</div>
              <p className="mt-1 text-xs text-slate-600">Настройки → Устройства → Подключить устройство</p>
              <div className="mt-2 flex justify-center">
                <img src={qrState.qrDataUrl} alt="QR" className="rounded border bg-white p-2" />
              </div>
              <p className="mt-2 text-xs text-slate-500">Ожидание сканирования…</p>
            </div>
          ) : null}
          {qrState.status === "2fa_required" ? (
            <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-4">
              <div className="text-sm font-medium text-amber-800">Требуется пароль 2FA</div>
              <p className="mt-1 text-xs text-amber-700">Введите пароль облачного пароля Telegram.</p>
              <div className="mt-2 flex gap-2">
                <input
                  type="password"
                  className="flex-1 rounded border border-amber-300 px-3 py-2 text-sm"
                  placeholder="Пароль 2FA"
                  value={qr2faPassword}
                  onChange={(e) => setQr2faPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleQr2faSubmit()}
                />
                <button
                  className="rounded bg-amber-600 px-3 py-2 text-sm text-white hover:bg-amber-700"
                  onClick={handleQr2faSubmit}
                  disabled={!qr2faPassword.trim()}
                >
                  Подтвердить
                </button>
              </div>
            </div>
          ) : null}
          {qrState.status === "done" && qrState.sessionString ? (
            <div className="mt-3 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              Session string получен и подставлен в форму выше. Нажмите «Сохранить».
            </div>
          ) : null}
          {qrState.status === "error" || qrState.status === "timeout" ? (
            <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">
              {qrState.error}
            </div>
          ) : null}
          {saveError ? <div className="mt-2 text-sm text-red-600">{saveError}</div> : null}
        {!isAdmin ? (
          <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
            Сохранение доступно только роли Admin.
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex gap-2">
        <button
          className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
          onClick={reload}
          disabled={loading}
        >
          Обновить статус
        </button>
      </div>

      {error ? (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>
      ) : null}

      {status ? (
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded border bg-white p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Учётные данные</div>
            <div className="mt-2">
              <StatusBadge ok={status.credentials_configured} label={status.credentials_configured ? "Настроены" : "Не настроены"} />
            </div>
          </div>
          <div className="rounded border bg-white p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Способ авторизации</div>
            <div className="mt-2">
              <StatusBadge ok={status.session_string_used} label={status.session_string_used ? "Session string" : "Файл / tg-auth"} />
            </div>
          </div>
          <div className="rounded border bg-white p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Session-файл</div>
            <div className="mt-2">
              <StatusBadge ok={status.session_file_exists || status.session_string_used} label={status.session_string_used ? "Не нужен" : status.session_file_exists ? "Найден" : "Не найден"} />
            </div>
          </div>
          <div className="rounded border bg-white p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Авторизация (проверка подключения)</div>
            <div className="mt-2">
              {status.session_authorized === null ? (
                <div className="flex items-center gap-2 text-slate-600">
                  <AlertCircle className="h-5 w-5" />
                  <span>Проверка недоступна</span>
                </div>
              ) : (
                <StatusBadge ok={status.session_authorized} label={status.session_authorized ? "Авторизован" : "Не авторизован"} />
              )}
            </div>
            {status.verify_error ? (
              <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                {status.verify_error}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="text-sm font-semibold">Источники</h2>
        <p className="mt-1 text-sm text-slate-600">
          В разделе «Источники» создайте источник типа <b>TELEGRAM_CHANNEL</b> и укажите username канала (например, <code className="rounded bg-slate-100 px-1">@channelname</code>).
        </p>
      </div>
    </div>
  );
}
