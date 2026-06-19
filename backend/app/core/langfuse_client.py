"""
Langfuse observability client — lazy singleton with NoopTracer fallback.

When LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are absent or are stub
values (pk-lf-stub, pk-lf-fake, etc.) this module returns a _NoopClient
whose methods accept the same arguments as the real Langfuse SDK but do
nothing.

Guarantees:
  - The rest of the codebase can always call get_langfuse() without
    checking whether tracing is enabled.
  - The app never crashes because of missing / invalid credentials.
  - In V1 (stub keys) every call is a silent no-op.
  - In V2 (real keys) every Claude call is automatically traced.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Keys that indicate Langfuse has not been configured with real credentials.
_STUB_PREFIXES = (
    "pk-lf-stub",
    "sk-lf-stub",
    "pk-lf-fake",
    "sk-lf-fake",
    "pk-lf-...",
    "sk-lf-...",
)


# ── Noop objects — mirror the Langfuse SDK surface used by reporter.py ────────


class _NoopGeneration:
    """Mirrors langfuse.client.StatefulGenerationClient — all methods are no-ops."""

    def update(self, **kwargs: Any) -> None:
        pass

    def end(self, **kwargs: Any) -> None:
        pass


class _NoopTrace:
    """Mirrors langfuse.client.StatefulTraceClient."""

    def generation(self, **kwargs: Any) -> _NoopGeneration:
        return _NoopGeneration()

    def update(self, **kwargs: Any) -> None:
        pass


class _NoopClient:
    """
    Returned when Langfuse credentials are missing or are stub values.
    Safe to call from anywhere — produces no network traffic.
    """

    def trace(self, **kwargs: Any) -> _NoopTrace:
        return _NoopTrace()

    def flush(self) -> None:
        pass


# ── Lazy singleton ────────────────────────────────────────────────────────────

_client: Any = None  # real Langfuse instance or _NoopClient


def get_langfuse() -> Any:
    """
    Return the module-level Langfuse client (real or noop).

    Initialised on first call; cached for the lifetime of the process.
    A brief race at startup is acceptable — worst case two Langfuse()
    instances are created; one is discarded.  After that writes are never
    made to _client, so no lock is needed.
    """
    global _client
    if _client is not None:
        return _client

    from app.config import settings  # deferred — avoids circular import at module load

    pub = settings.langfuse_public_key
    sec = settings.langfuse_secret_key

    is_stub = (
        not pub
        or not sec
        or any(pub.startswith(p) for p in _STUB_PREFIXES)
        or any(sec.startswith(p) for p in _STUB_PREFIXES)
    )

    if is_stub:
        logger.debug("Langfuse credentials are stubs — tracing disabled (NoopClient)")
        _client = _NoopClient()
        return _client

    try:
        from langfuse import Langfuse  # type: ignore[import]

        _client = Langfuse(
            public_key=pub,
            secret_key=sec,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse tracing enabled (host=%s)", settings.langfuse_host)
    except Exception as exc:
        logger.warning(
            "Langfuse initialisation failed: %s — falling back to NoopClient", exc
        )
        _client = _NoopClient()

    return _client
