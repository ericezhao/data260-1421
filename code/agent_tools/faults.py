"""Repository wrappers that inject failures, for retry demos and the fault-injection experiment."""

import random
import time

from retry import TransientError

HANG_S = 3.0  # longer than any policy timeout, so a "hang" always ends in a timeout


class _Wrapper:
    def __init__(self, inner):
        self.inner = inner

    def _before_call(self):
        raise NotImplementedError

    def search(self, query, cuisine, limit):
        self._before_call()
        return self.inner.search(query, cuisine, limit)

    def get_by_code(self, code):
        self._before_call()
        return self.inner.get_by_code(code)

    def score_summary(self, group_by, top):
        self._before_call()
        return self.inner.score_summary(group_by, top)


class FlakyRepository(_Wrapper):
    """Fails each storage call with probability `failure_rate`, decided by a seeded RNG.

    One draw decides fail/succeed and, on failure, a second draw picks the failure kind
    (80% immediate error, 20% hang until the timeout). The same seed always gives the same sequence.
    """

    def __init__(self, inner, failure_rate: float, seed: int, hang_s: float = HANG_S):
        super().__init__(inner)
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)
        self.hang_s = hang_s
        self.decisions: list[str] = []

    def _before_call(self):
        if self.rng.random() >= self.failure_rate:
            self.decisions.append("ok")
            return
        if self.rng.random() < 0.8:
            self.decisions.append("error")
            raise TransientError("injected fault: connection reset")
        self.decisions.append("hang")
        time.sleep(self.hang_s)


class ScriptedRepository(_Wrapper):
    """Follows a fixed plan such as ["error", "ok"]: attempt 1 fails, attempt 2 succeeds."""

    def __init__(self, inner, plan: list[str]):
        super().__init__(inner)
        self.plan = list(plan)

    def _before_call(self):
        step = self.plan.pop(0) if self.plan else "ok"
        if step == "error":
            raise TransientError("injected fault: connection reset")
        if step == "hang":
            time.sleep(HANG_S)
