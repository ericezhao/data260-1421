"""Timeouts plus bounded exponential-backoff retry for calls that may fail."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

# a timed-out call keeps running in its worker thread; the caller just stops waiting for it
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="retry")


class TransientError(Exception):
    """A failure worth retrying (network blip, lock timeout, injected fault)."""


class RetryExhausted(Exception):
    def __init__(self, attempts: int, last_error: BaseException):
        super().__init__(f"failed after {attempts} attempt(s): {last_error}")
        self.attempts = attempts
        self.last_error = last_error


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    timeout_s: float = 2.0
    base_delay_s: float = 0.1
    max_delay_s: float = 1.0
    retry_on: tuple[type[BaseException], ...] = (TransientError, TimeoutError)

    def delay_before(self, attempt: int) -> float:
        """Backoff before attempt 2, 3, ...: base, 2*base, 4*base, ... capped at max_delay_s."""
        return min(self.max_delay_s, self.base_delay_s * 2 ** (attempt - 2))


@dataclass
class Trace:
    attempts: list[dict[str, Any]] = field(default_factory=list)


def call_with_retry(
    fn: Callable[[], Any],
    policy: RetryPolicy = RetryPolicy(),
    trace: Trace | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    last_error: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        if attempt > 1:
            sleep(policy.delay_before(attempt))
        start = time.perf_counter()
        try:
            result = _executor.submit(fn).result(timeout=policy.timeout_s)
        except FutureTimeout:
            last_error = TimeoutError(f"timed out after {policy.timeout_s}s")
        except policy.retry_on as exc:
            last_error = exc
        else:
            _record(trace, attempt, start, "ok")
            return result
        _record(trace, attempt, start, f"{type(last_error).__name__}: {last_error}")
        log.warning("attempt %d/%d failed: %s", attempt, policy.max_attempts, last_error)
    raise RetryExhausted(policy.max_attempts, last_error)


def _record(trace: Trace | None, attempt: int, start: float, outcome: str) -> None:
    if trace is not None:
        trace.attempts.append(
            {
                "attempt": attempt,
                "outcome": outcome,
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
