"""
ベンチとパイプラインの所要時間。採点にはまだ使わない。記録だけする。

timing:
  total_seconds          全体の壁時計
  llm_seconds            chat() の合計
  machine_seconds        total - llm
  research_seconds       調査工程
  judge_seconds          要求充足の判断
  implementation_seconds 実装工程
  repair_seconds         修復工程
  validation_seconds     Validator / 実行確認
"""

import contextvars
import time
from contextlib import contextmanager, nullcontext


STAGES = (
    "research",
    "judge",
    "implementation",
    "repair",
    "validation",
)

_active = contextvars.ContextVar("pipeline_timing", default=None)


def round_seconds(value):
    return round(max(0.0, float(value)), 1)


def empty_timing():
    payload = {
        "total_seconds": 0.0,
        "llm_seconds": 0.0,
        "machine_seconds": 0.0,
    }
    for name in STAGES:
        payload[f"{name}_seconds"] = 0.0
    return payload


class Timing:
    def __init__(self):
        self._started = time.perf_counter()
        self._llm = 0.0
        self._llm_calls = 0
        self._stages = {name: 0.0 for name in STAGES}
        self._token = None

    def __enter__(self):
        self._started = time.perf_counter()
        self._token = _active.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            _active.reset(self._token)
            self._token = None
        return False

    def add_llm(self, seconds):
        if seconds is None:
            return
        self._llm += max(0.0, float(seconds))
        self._llm_calls += 1

    def add_stage(self, name, seconds):
        if name not in self._stages or seconds is None:
            return
        self._stages[name] += max(0.0, float(seconds))

    @contextmanager
    def stage(self, name):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.add_stage(name, time.perf_counter() - started)

    def snapshot(self):
        total = time.perf_counter() - self._started
        llm = self._llm
        payload = empty_timing()
        payload["total_seconds"] = round_seconds(total)
        payload["llm_seconds"] = round_seconds(llm)
        payload["machine_seconds"] = round_seconds(total - llm)
        payload["llm_calls"] = self._llm_calls
        for name in STAGES:
            payload[f"{name}_seconds"] = round_seconds(self._stages[name])
        return payload


def current_timing():
    return _active.get()


def record_llm(seconds):
    clock = current_timing()
    if clock is not None:
        clock.add_llm(seconds)


def stage(name):
    clock = current_timing()
    if clock is None:
        return nullcontext()
    return clock.stage(name)
