import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../state/auth";
import { HelpText, HintBox } from "../components/Field";

export function LoginPage() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md rounded-lg border bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold">Вход</h1>
        <p className="mt-1 text-sm text-slate-600">Только для администраторов.</p>

        {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

        <div className="mt-4 space-y-3">
          <label className="block">
            <div className="text-sm text-slate-700">Email</div>
            <input
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@company.ru"
              autoComplete="email"
            />
            <HelpText>Логин — это email в формате <code className="rounded bg-slate-100 px-1">name@domain</code>.</HelpText>
          </label>
          <label className="block">
            <div className="text-sm text-slate-700">Пароль</div>
            <input
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
              type="password"
              autoComplete="current-password"
            />
            <HelpText>Минимум 8 символов. Рекомендуем: 12+ символов, буквы/цифры/символы.</HelpText>
          </label>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            className="flex-1 rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                await login(email, password);
                nav("/regions");
              } catch (e: any) {
                setError(e?.message || "Ошибка входа");
              } finally {
                setBusy(false);
              }
            }}
          >
            Войти
          </button>
        </div>

        <hr className="my-6" />

        <h2 className="text-sm font-semibold">Первичный админ (dev)</h2>
        <HintBox>
          <div className="font-medium">Когда доступно</div>
          <ul className="mt-1 list-disc pl-4">
            <li>Только в dev (когда <code className="rounded bg-white px-1">APP_ENV</code> не равен <code className="rounded bg-white px-1">prod</code>).</li>
            <li>Только если пользователей в базе ещё нет.</li>
          </ul>
          <div className="mt-2 text-slate-600">
            Endpoint: <code className="rounded bg-white px-1">POST /api/admin/bootstrap</code>
          </div>
        </HintBox>

        <label className="mt-3 block">
          <div className="text-sm text-slate-700">ФИО (опционально)</div>
          <input className="mt-1 w-full rounded border px-3 py-2 text-sm" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <HelpText>Отображается в аудит-логах и в будущих отчётах как “кто создал”.</HelpText>
        </label>

        <button
          className="mt-3 w-full rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await api.auth.bootstrapAdmin(email, password, fullName || undefined);
              await login(email, password);
              nav("/regions");
            } catch (e: any) {
              setError(e?.message || "Ошибка bootstrap");
            } finally {
              setBusy(false);
            }
          }}
        >
          Создать первого Admin (только dev)
        </button>
      </div>
    </div>
  );
}

