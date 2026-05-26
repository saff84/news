"""AI client (OpenRouter + RouterAI) with request/response validation."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger("services.ai_client")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ROUTERAI_URL = "https://routerai.ru/api/v1/chat/completions"
MAX_CONTENT_LENGTH = 100_000  # truncate data if too long
MIN_RESPONSE_LENGTH = 1
MAX_RESPONSE_LENGTH = 100_000


class AIValidationError(Exception):
    """Validation failed for request or response."""

    pass


def _truncate(text: str, max_len: int = MAX_CONTENT_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n[... обрезано ...]"


def validate_request(
    *,
    api_key: str,
    model: str,
    prompt: str,
    data: str,
) -> None:
    """Validate request before sending to AI. Raises AIValidationError if invalid."""
    if not api_key or not api_key.strip():
        raise AIValidationError("API ключ не задан")
    if not model or not model.strip():
        raise AIValidationError("Модель не задана")
    if not prompt or not prompt.strip():
        raise AIValidationError("Промпт не задан")
    if not isinstance(data, str):
        raise AIValidationError("Данные должны быть строкой")


def validate_response(response: dict[str, Any]) -> str:
    """
    Validate AI response and extract content.
    Raises AIValidationError if invalid.
    Returns the content string.
    """
    if not isinstance(response, dict):
        raise AIValidationError("Ответ ИИ не является объектом")

    choices = response.get("choices")
    if not choices or not isinstance(choices, list):
        raise AIValidationError("Ответ ИИ: отсутствует choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise AIValidationError("Ответ ИИ: неверный формат choices[0]")

    message = first.get("message")
    if not message or not isinstance(message, dict):
        raise AIValidationError("Ответ ИИ: отсутствует message")

    content = message.get("content")
    if content is None:
        raise AIValidationError("Ответ ИИ: отсутствует content")

    text = str(content).strip()
    if len(text) < MIN_RESPONSE_LENGTH:
        raise AIValidationError("Ответ ИИ пуст или слишком короткий")
    if len(text) > MAX_RESPONSE_LENGTH:
        raise AIValidationError("Ответ ИИ превышает допустимый размер")

    return text


def call_openrouter(
    *,
    api_key: str,
    model: str,
    prompt: str,
    data: str,
    timeout: float = 60.0,
) -> str:
    """
    Call OpenRouter chat completions.
    Combines prompt + data into user message.
    Returns validated content string.
    """
    validate_request(api_key=api_key, model=model, prompt=prompt, data=data)

    data_truncated = _truncate(data)
    user_content = f"{prompt.strip()}\n\n--- Данные ---\n\n{data_truncated}"

    payload = {
        "model": model.strip(),
        "messages": [{"role": "user", "content": user_content}],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        try:
            err_body = resp.json()
            err_msg = err_body.get("error", {}).get("message", str(err_body))
        except Exception:
            err_msg = resp.text or resp.reason_phrase
        raise AIValidationError(f"Ошибка ИИ ({resp.status_code}): {err_msg}")

    try:
        body = resp.json()
    except Exception as e:
        raise AIValidationError(f"Не удалось разобрать ответ ИИ: {e}")

    return validate_response(body)


def call_provider(
    *,
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    data: str,
    timeout: float = 60.0,
    max_retries: int = 0,
    retry_base_seconds: float = 5.0,
    log_label: str = "ai",
) -> str:
    """
    Call configured AI provider using OpenAI-compatible Chat Completions format.
    Supported providers:
    - openrouter: https://openrouter.ai/api/v1/chat/completions
    - routerai:   https://routerai.ru/api/v1/chat/completions
    """
    provider_norm = (provider or "openrouter").strip().lower()
    if provider_norm == "openrouter":
        url = OPENROUTER_URL
    elif provider_norm == "routerai":
        url = ROUTERAI_URL
    else:
        raise AIValidationError(f"Неизвестный AI provider: {provider}")

    validate_request(api_key=api_key, model=model, prompt=prompt, data=data)
    data_truncated = _truncate(data)
    user_content = f"{prompt.strip()}\n\n--- Данные ---\n\n{data_truncated}"
    payload = {
        "model": model.strip(),
        "messages": [{"role": "user", "content": user_content}],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    attempts = max(0, int(max_retries)) + 1
    last_error: AIValidationError | None = None

    for attempt in range(attempts):
        t0 = time.perf_counter()
        log.info(
            "AI request start label=%s provider=%s model=%s attempt=%s/%s",
            log_label,
            provider_norm,
            model.strip(),
            attempt + 1,
            attempts,
        )
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key.strip()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if resp.status_code == 200:
            try:
                body = resp.json()
            except Exception as e:
                log.error("AI response parse failed label=%s ms=%s err=%s", log_label, elapsed_ms, e)
                raise AIValidationError(f"Не удалось разобрать ответ ИИ: {e}") from e
            text = validate_response(body)
            log.info("AI request ok label=%s ms=%s chars=%s", log_label, elapsed_ms, len(text))
            return text

        try:
            err_body = resp.json()
            err_msg = err_body.get("error", {}).get("message", str(err_body))
        except Exception:
            err_msg = resp.text or resp.reason_phrase or "unknown error"

        last_error = AIValidationError(f"Ошибка ИИ ({resp.status_code}): {err_msg}")
        log.warning(
            "AI request failed label=%s status=%s ms=%s attempt=%s/%s msg=%s",
            log_label,
            resp.status_code,
            elapsed_ms,
            attempt + 1,
            attempts,
            err_msg,
        )

        if resp.status_code == 429 and attempt < attempts - 1:
            wait_s = retry_base_seconds * (2**attempt)
            log.info("AI rate limit 429, retry in %.1fs label=%s", wait_s, log_label)
            time.sleep(wait_s)
            continue
        break

    assert last_error is not None
    raise last_error
