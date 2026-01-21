"""Shared HTTP utilities for providers."""

from __future__ import annotations

import asyncio
from typing import Iterable

import httpx

from .base import ProviderError

_RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504}


def _parse_retry_after_seconds(resp: httpx.Response) -> float | None:
    ra = resp.headers.get("retry-after")
    if not ra:
        return None
    try:
        return max(0.0, float(ra.strip()))
    except ValueError:
        return None


def _extract_error_message(resp: httpx.Response) -> str:
    msg = None
    try:
        data = resp.json()
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            raw = err.get("message")
            if isinstance(raw, str) and raw.strip():
                msg = raw.strip()
    except Exception:
        msg = None

    if msg is None:
        body = (resp.text or "").strip()
        msg = body[:500] if body else "(no response body)"
    return msg


def _format_http_error(
    resp: httpx.Response,
    provider_label: str,
    request_id_headers: Iterable[str],
) -> str:
    request_id = None
    for header in request_id_headers:
        value = resp.headers.get(header)
        if value:
            request_id = value
            break

    retry_after = _parse_retry_after_seconds(resp)
    msg = _extract_error_message(resp)

    parts = [f"{provider_label} API error {resp.status_code}: {msg}"]
    if request_id:
        parts.append(f"request_id={request_id}")
    if retry_after is not None:
        parts.append(f"retry_after_seconds={retry_after:.0f}")
    if len(parts) == 1:
        return parts[0]
    return parts[0] + " (" + ", ".join(parts[1:]) + ")"


async def post_json_with_retries(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: httpx.Timeout | None,
    max_retries: int,
    backoff_base_seconds: float,
    provider_label: str,
    request_id_headers: Iterable[str],
    retryable_statuses: set[int] | None = None,
) -> httpx.Response:
    """POST JSON with retry/backoff behavior and consistent ProviderError messages."""
    retryable = retryable_statuses or _RETRYABLE_STATUSES
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 2):
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=timeout)

            if resp.status_code >= 400:
                if resp.status_code in retryable and attempt <= max_retries:
                    retry_after = _parse_retry_after_seconds(resp)
                    delay = retry_after if retry_after is not None else (backoff_base_seconds * (2 ** (attempt - 1)))
                    await asyncio.sleep(delay)
                    continue
                raise ProviderError(_format_http_error(resp, provider_label, request_id_headers))

            return resp

        except ProviderError:
            raise
        except httpx.TimeoutException as e:
            last_err = e
            if attempt <= max_retries:
                await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))
                continue
            raise ProviderError(f"{provider_label} request timed out: {e}")
        except httpx.RequestError as e:
            last_err = e
            if attempt <= max_retries:
                await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))
                continue
            raise ProviderError(f"{provider_label} request failed: {e}")
        except Exception as e:
            last_err = e
            if attempt <= max_retries:
                await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))
                continue
            raise ProviderError(f"{provider_label} provider failed after retries: {last_err}")

    if isinstance(last_err, httpx.TimeoutException):
        raise ProviderError(f"{provider_label} request timed out: {last_err}")
    if isinstance(last_err, httpx.RequestError):
        raise ProviderError(f"{provider_label} request failed: {last_err}")
    raise ProviderError(f"{provider_label} provider failed after retries: {last_err}")
