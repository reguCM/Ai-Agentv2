"""Ollama call for Grill observation. Does not use production llm.chat."""
from __future__ import annotations

import threading
import time
from typing import Any

from ollama import Client


def message_content(resp: Any) -> str:
    msg = resp.get("message") if isinstance(resp, dict) else getattr(resp, "message", None)
    if isinstance(msg, dict):
        return str(msg.get("content") or "")
    return str(getattr(msg, "content", "") or "")


def call_local(
    *,
    model: str,
    messages: list[dict[str, str]],
    num_ctx: int,
    num_predict: int,
    temperature: float,
    timeout_s: int,
    label: str = "grill_q",
) -> dict[str, Any]:
    client = Client(timeout=timeout_s)
    started = time.perf_counter()
    error = None
    resp = None
    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(15):
            elapsed = time.perf_counter() - started
            print(f"HEARTBEAT {label} elapsed_s={elapsed:.0f} timeout_s={timeout_s}", flush=True)

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    try:
        print(
            f"CALL {label} model={model} num_ctx={num_ctx} num_predict={num_predict} timeout_s={timeout_s}",
            flush=True,
        )
        resp = client.chat(
            model=model,
            messages=messages,
            format="json",
            options={
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
            keep_alive="10m",
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(f"ERROR {label} {error}", flush=True)
    finally:
        stop.set()
    wall_s = round(time.perf_counter() - started, 3)
    raw = "" if resp is None else message_content(resp)
    print(f"DONE {label} wall_s={wall_s} error={error}", flush=True)
    return {
        "elapsed_s": wall_s,
        "error": error,
        "raw_text": raw,
    }
