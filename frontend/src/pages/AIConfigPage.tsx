import { useEffect, useState } from "react";
import { Bot, Key, Play, Save } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../state/auth";
import { useToast } from "../state/toast";
import { HintBox } from "../components/Field";

type AIConfig = {
  provider: string;
  api_key_set: boolean;
  model: string;
  ai_request_delay_seconds: number;
  ai_max_retries: number;
  ai_retry_base_seconds: number;
  prompt_news: string;
  prompt_competitors: string;
  prompt_competitor_tg: string;
  prompt_developers: string;
  prompt_indicators: string;
  prompt_regions: string;
  prompt_clusters: string;
};

/** Популярные модели OpenRouter (https://openrouter.ai/models) */
const OPENROUTER_MODELS = [
  { id: "openai/gpt-4o-mini", label: "GPT-4o Mini (OpenAI)" },
  { id: "openai/gpt-4o", label: "GPT-4o (OpenAI)" },
  { id: "openai/gpt-4-turbo", label: "GPT-4 Turbo (OpenAI)" },
  { id: "anthropic/claude-3.5-haiku", label: "Claude 3.5 Haiku (Anthropic)" },
  { id: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet (Anthropic)" },
  { id: "anthropic/claude-3-opus", label: "Claude 3 Opus (Anthropic)" },
  { id: "google/gemini-2.0-flash-exp:free", label: "Gemini 2.0 Flash (Google, free)" },
  { id: "google/gemini-pro", label: "Gemini Pro (Google)" },
  { id: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B (Meta)" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek Chat" },
];

/** Примеры моделей для RouterAI (OpenAI-compatible endpoint). */
const ROUTERAI_MODELS = [
  { id: "openai/gpt-4o-mini", label: "GPT-4o Mini" },
  { id: "openai/gpt-4o", label: "GPT-4o" },
  { id: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet" },
  { id: "google/gemini-2.0-flash-exp", label: "Gemini 2.0 Flash" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek Chat" },
];

const PROMPT_KEYS = ["prompt_news", "prompt_competitors", "prompt_competitor_tg", "prompt_developers", "prompt_indicators", "prompt_regions", "prompt_clusters"] as const;

const PROMPT_LABELS: Record<(typeof PROMPT_KEYS)[number], { label: string; hint: string }> = {
  prompt_news: {
    label: "Общие новости",
    hint: "Промпт для сводки по важным новостям (без пометки конкурентов).",
  },
  prompt_competitors: {
    label: "Новости конкурентов",
    hint: "Промпт для выдержки по новостям конкурентов: какие новинки представили, что происходило в компании. Данные приходят с пометкой [Название компании].",
  },
  prompt_competitor_tg: {
    label: "TG-архив конкурентов",
    hint: "Саммари по постам TG-канала конкурента (до 24 мес.). Новинки ассортимента и продуктовые анонсы нельзя вырезать — к промпту всегда добавляется жёсткое правило сохранности продуктового контента.",
  },
  prompt_developers: {
    label: "Застройщики",
    hint: "Промпт для саммари по новостям застройщиков (отдельная сущность). Во входе — публикации с Markdown-ссылками на источники; в ответе тоже используйте [текст](url). Если пусто, используется промпт конкурентов.",
  },
  prompt_indicators: {
    label: "Индикаторы",
    hint: "Промпт для анализа индикаторов (курсы, показатели). В отчёт подставляются данные индикаторов.",
  },
  prompt_regions: {
    label: "Регионы",
    hint: "Промпт для сводки по регионам. В отчёт подставляются данные по регионам.",
  },
  prompt_clusters: {
    label: "Кластеры новостей",
    hint: "Промпт для анализа кластеров/групп новостей. В отчёт подставляются сгруппированные новости.",
  },
};

export function AIConfigPage() {
  const { accessToken, user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.role === "Admin";

  const [config, setConfig] = useState<AIConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AIConfig & { api_key: string }>({
    provider: "openrouter",
    api_key_set: false,
    api_key: "",
    model: "openai/gpt-4o-mini",
    ai_request_delay_seconds: 2,
    ai_max_retries: 3,
    ai_retry_base_seconds: 5,
    prompt_news: "",
    prompt_competitors: "",
    prompt_competitor_tg: "",
    prompt_developers: "",
    prompt_indicators: "",
    prompt_regions: "",
    prompt_clusters: "",
  });
  const [modelCustom, setModelCustom] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [testBusy, setTestBusy] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
    latency_ms: number;
    response_preview: string | null;
  } | null>(null);
  const provider = (form.provider || "openrouter").toLowerCase();
  const providerModels = provider === "routerai" ? ROUTERAI_MODELS : OPENROUTER_MODELS;

  const reload = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const c = await api.aiConfig.get(accessToken);
      setConfig(c);
      const currentProvider = (c.provider || "openrouter").toLowerCase();
      const presetModels = currentProvider === "routerai" ? ROUTERAI_MODELS : OPENROUTER_MODELS;
      const isPreset = presetModels.some((m) => m.id === c.model);
      setForm((f) => ({
        ...f,
        provider: currentProvider,
        api_key_set: c.api_key_set,
        api_key: "", // never prefill for security
        model: c.model,
        ai_request_delay_seconds: c.ai_request_delay_seconds ?? 2,
        ai_max_retries: c.ai_max_retries ?? 3,
        ai_retry_base_seconds: c.ai_retry_base_seconds ?? 5,
        prompt_news: c.prompt_news ?? "",
        prompt_competitors: c.prompt_competitors ?? "",
        prompt_competitor_tg: c.prompt_competitor_tg ?? "",
        prompt_developers: c.prompt_developers ?? "",
        prompt_indicators: c.prompt_indicators ?? "",
        prompt_regions: c.prompt_regions ?? "",
        prompt_clusters: c.prompt_clusters ?? "",
      }));
      setModelCustom(!isPreset);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
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
    setSaveSuccess(false);
    try {
      const payload: Parameters<typeof api.aiConfig.update>[1] = {
        provider: form.provider,
        model: form.model,
        ai_request_delay_seconds: form.ai_request_delay_seconds,
        ai_max_retries: form.ai_max_retries,
        ai_retry_base_seconds: form.ai_retry_base_seconds,
        prompt_news: form.prompt_news,
        prompt_competitors: form.prompt_competitors,
        prompt_competitor_tg: form.prompt_competitor_tg,
        prompt_developers: form.prompt_developers,
        prompt_indicators: form.prompt_indicators,
        prompt_regions: form.prompt_regions,
        prompt_clusters: form.prompt_clusters,
      };
      // Only send api_key when user changed it (typed new or cleared)
      if (form.api_key !== "" || form.api_key_set) payload.api_key = form.api_key;
      await api.aiConfig.update(accessToken, payload);
      setSaveSuccess(true);
      reload();
      setTimeout(() => setSaveSuccess(false), 3000);
      push({ variant: "success", title: "Сохранено", description: "Настройки ИИ обновлены" });
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
      <h1 className="text-lg font-semibold">Подключение ИИ</h1>
      <p className="mt-1 text-sm text-slate-600">
        Промпты для обработки собранной информации. Для каждого типа данных задаётся свой промпт — он будет использоваться при генерации аналитики и отчётов.
      </p>

      <HintBox>
        <div className="font-medium">Примечание</div>
        <div className="mt-1">
          Настройки используются при генерации отчёта. Можно переключаться между OpenRouter и RouterAI без изменения остального пайплайна.
        </div>
      </HintBox>

      {error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}

      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Key className="h-4 w-4" />
          Провайдер и доступ
        </h2>
        <div className="mt-3">
          <div className="text-sm text-slate-700">Сервис</div>
          <div className="mt-1 flex flex-wrap gap-2">
            <button
              type="button"
              className={`rounded border px-3 py-2 text-sm ${provider === "openrouter" ? "border-slate-900 bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"}`}
              onClick={() => {
                setForm((f) => ({ ...f, provider: "openrouter", model: OPENROUTER_MODELS[0].id }));
                setModelCustom(false);
              }}
              disabled={!isAdmin}
            >
              OpenRouter
            </button>
            <button
              type="button"
              className={`rounded border px-3 py-2 text-sm ${provider === "routerai" ? "border-slate-900 bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"}`}
              onClick={() => {
                setForm((f) => ({ ...f, provider: "routerai", model: ROUTERAI_MODELS[0].id }));
                setModelCustom(false);
              }}
              disabled={!isAdmin}
            >
              RouterAI
            </button>
          </div>
        </div>
        <p className="mt-1 text-xs text-slate-600">
          {provider === "routerai" ? (
            <>
              RouterAI: единый OpenAI-совместимый API через endpoint <code>https://routerai.ru/api/v1</code>. Документация:{" "}
              <a href="https://routerai.ru/docs/guides" target="_blank" rel="noopener noreferrer" className="text-slate-800 underline">
                routerai.ru/docs/guides
              </a>
              .
            </>
          ) : (
            <>
              OpenRouter: доступ к моделям OpenAI, Anthropic, Google и др. Ключ можно получить на{" "}
              <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-slate-800 underline">
                openrouter.ai/keys
              </a>
              .
            </>
          )}
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="min-w-0 flex-1">
            <span className="text-sm text-slate-700">API ключ</span>
            <input
              type="password"
              className="mt-1 w-full max-w-md rounded border px-3 py-2 font-mono text-sm"
              value={form.api_key}
              onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
              placeholder={form.api_key_set ? "Ключ сохранён — введите новый, чтобы заменить" : provider === "routerai" ? "ra_..." : "sk-or-v1-..."}
              disabled={!isAdmin}
              autoComplete="off"
            />
          </label>
          {form.api_key_set && isAdmin ? (
            <button
              type="button"
              className="rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => setForm((f) => ({ ...f, api_key: "" }))}
            >
              Удалить ключ
            </button>
          ) : null}
        </div>
        <label className="mt-3 block">
          <span className="text-sm text-slate-700">Модель</span>
          <p className="mt-0.5 text-xs text-slate-500">
            {provider === "routerai" ? (
              <>
                ID модели из каталога RouterAI (или совместимый идентификатор).
              </>
            ) : (
              <>
                ID модели из{" "}
                <a href="https://openrouter.ai/models" target="_blank" rel="noopener noreferrer" className="underline">
                  openrouter.ai/models
                </a>
              </>
            )}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <select
              className="rounded border px-3 py-2 text-sm"
              value={modelCustom ? "__custom__" : form.model}
              onChange={(e) => {
                const v = e.target.value;
                if (v === "__custom__") {
                  setModelCustom(true);
                } else {
                  setModelCustom(false);
                  setForm((f) => ({ ...f, model: v }));
                }
              }}
              disabled={!isAdmin}
            >
              {providerModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
              <option value="__custom__">Другая (ввести вручную)</option>
            </select>
            {modelCustom ? (
              <input
                type="text"
                className="min-w-[200px] rounded border px-3 py-2 font-mono text-sm"
                value={form.model}
                onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
                placeholder="openai/gpt-4o-mini"
                disabled={!isAdmin}
              />
            ) : null}
          </div>
        </label>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <label className="block">
            <span className="text-sm text-slate-700">Пауза между запросами (сек)</span>
            <input
              type="number"
              min={0}
              max={120}
              step={0.5}
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.ai_request_delay_seconds}
              onChange={(e) => setForm((f) => ({ ...f, ai_request_delay_seconds: parseFloat(e.target.value) || 0 }))}
              disabled={!isAdmin}
            />
            <p className="mt-1 text-xs text-slate-500">Снижает 429 при генерации отчёта (конкуренты, регионы…)</p>
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Повторы при 429</span>
            <input
              type="number"
              min={0}
              max={10}
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.ai_max_retries}
              onChange={(e) => setForm((f) => ({ ...f, ai_max_retries: parseInt(e.target.value, 10) || 0 }))}
              disabled={!isAdmin}
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">База ожидания retry (сек)</span>
            <input
              type="number"
              min={1}
              max={300}
              step={1}
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
              value={form.ai_retry_base_seconds}
              onChange={(e) => setForm((f) => ({ ...f, ai_retry_base_seconds: parseFloat(e.target.value) || 5 }))}
              disabled={!isAdmin}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
            disabled={!isAdmin || testBusy}
            onClick={async () => {
              if (!accessToken) return;
              setTestBusy(true);
              setTestResult(null);
              try {
                if (isAdmin) {
                  await api.aiConfig.update(accessToken, {
                    provider: form.provider,
                    model: form.model,
                    ai_request_delay_seconds: form.ai_request_delay_seconds,
                    ai_max_retries: form.ai_max_retries,
                    ai_retry_base_seconds: form.ai_retry_base_seconds,
                    ...(form.api_key !== "" || form.api_key_set ? { api_key: form.api_key } : {}),
                  });
                }
                const r = await api.aiConfig.test(accessToken);
                setTestResult({
                  ok: r.ok,
                  message: r.message,
                  latency_ms: r.latency_ms,
                  response_preview: r.response_preview,
                });
                push({
                  variant: r.ok ? "success" : "error",
                  title: r.ok ? "ИИ доступен" : "Ошибка ИИ",
                  description: r.message,
                });
              } catch (e: unknown) {
                const msg = e instanceof Error ? e.message : "Тест не удался";
                setTestResult({ ok: false, message: msg, latency_ms: 0, response_preview: null });
                push({ variant: "error", title: "Тест ИИ", description: msg });
              } finally {
                setTestBusy(false);
              }
            }}
          >
            <Play className="h-4 w-4" />
            {testBusy ? "Проверка…" : "Тест подключения"}
          </button>
          <span className="text-xs text-slate-500">Логи: docker compose logs backend -f | findstr AI</span>
        </div>
        {testResult ? (
          <div
            className={`mt-3 rounded border p-3 text-sm ${testResult.ok ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-800"}`}
          >
            <div className="font-medium">{testResult.ok ? "OK" : "Ошибка"}</div>
            <div className="mt-1">{testResult.message}</div>
            {testResult.latency_ms > 0 ? <div className="mt-1 text-xs opacity-80">Задержка: {testResult.latency_ms} мс</div> : null}
            {testResult.response_preview ? (
              <pre className="mt-2 max-h-24 overflow-auto rounded bg-white/60 p-2 text-xs">{testResult.response_preview}</pre>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 space-y-6">
        {PROMPT_KEYS.map((key) => (
          <div key={key} className="rounded border bg-white p-4">
            <h2 className="text-sm font-semibold">{PROMPT_LABELS[key].label}</h2>
            <p className="mt-1 text-xs text-slate-600">{PROMPT_LABELS[key].hint}</p>
            <textarea
              className="mt-2 min-h-[120px] w-full rounded border px-3 py-2 font-mono text-sm"
              value={(form[key as keyof typeof form] as string) ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              placeholder={`Введите промпт для обработки ${PROMPT_LABELS[key].label.toLowerCase()}…`}
              disabled={!isAdmin}
              rows={5}
            />
          </div>
        ))}
      </div>

      <div className="mt-6 flex gap-2">
        <button
          className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
          onClick={handleSave}
          disabled={saveBusy || !isAdmin}
        >
          <Save className="h-4 w-4" />
          Сохранить
        </button>
        {saveSuccess ? <span className="text-sm text-emerald-600">Сохранено</span> : null}
      </div>
      {!isAdmin ? (
        <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          Редактирование доступно только роли Admin.
        </div>
      ) : null}
    </div>
  );
}
