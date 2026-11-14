"""Minimal HTTP text fetcher with retries for the ingestion repositories.

Only httpx (already a dependency) and the standard library are used. The
single-purpose helper keeps timeouts and retry behavior identical across
the IDEAM and FIRMS repositories.
"""

from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 12.0
DEFAULT_RETRIES = 2
RETRY_BACKOFF_BASE_SECONDS = 0.35
CLIENT_USER_AGENT = "NASA-Fire-Harmonization-API/0.1"

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


async def fetch_text_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
) -> httpx.Response:
    """GET a URL and return the response, retrying transient upstream failures."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(url, timeout=timeout_seconds)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < retries:
                await _sleep_backoff(attempt)
                continue
            return response
        except httpx.TransportError as error:
            last_error = error
            if attempt < retries:
                await _sleep_backoff(attempt)
                continue
            raise
    raise last_error or RuntimeError(f"Request failed for {url}")


async def _sleep_backoff(attempt: int) -> None:
    import asyncio

    await asyncio.sleep(RETRY_BACKOFF_BASE_SECONDS * (attempt + 1))


def build_ssl_context(verify: bool = True) -> Any:
    """Build the TLS context for an HTTP client.

    ``verify=False`` is only justified for hosts with a known incomplete
    certificate chain (the IDEAM portal omits an intermediate CA
    certificate, as documented in the reference application).
    """
    if verify:
        return True
    import ssl

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context
