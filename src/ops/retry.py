"""Shared retry/backoff for external HTTP calls."""

from __future__ import annotations

import functools
import logging
import time
from typing import Callable, Iterable, Optional, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_BACKOFF = (2.0, 4.0, 8.0)


def with_retry(
    *,
    max_attempts: int = 3,
    backoff: Iterable[float] = DEFAULT_BACKOFF,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    label: str = "",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry on transient failures. Does not retry on the final attempt."""

    delays = tuple(float(x) for x in backoff)

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            name = label or fn.__qualname__
            last: Optional[BaseException] = None
            attempts = max(1, int(max_attempts))
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last = exc
                    if attempt >= attempts:
                        break
                    wait = delays[min(attempt - 1, len(delays) - 1)] if delays else 0
                    log.warning(
                        "%s failed attempt %s/%s: %s — retry in %.0fs",
                        name,
                        attempt,
                        attempts,
                        exc,
                        wait,
                    )
                    if wait > 0:
                        time.sleep(wait)
            assert last is not None
            log.error("%s failed after %s attempts: %s", name, attempts, last)
            raise last

        return wrapper

    return decorator


def call_with_retry(
    fn: Callable[..., T],
    *args,
    max_attempts: int = 3,
    backoff: Iterable[float] = DEFAULT_BACKOFF,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    label: str = "",
    **kwargs,
) -> T:
    return with_retry(
        max_attempts=max_attempts,
        backoff=backoff,
        exceptions=exceptions,
        label=label or getattr(fn, "__qualname__", "call"),
    )(fn)(*args, **kwargs)
