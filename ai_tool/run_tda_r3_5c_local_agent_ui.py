#!/usr/bin/env python3
"""R3.5-C: Chat API 経由で実LLM / モデル切替 / 履歴 / Event を実測する。

Cursor の mock テスト成功は Local Agent 成功に数えない。
このスクリプトは http://127.0.0.1:8765 の Chat API を叩く。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow

BASE = "http://127.0.0.1:8765"
TIMEOUT_CHAT = 180


def _request(method: str, path: str, payload: dict | None = None, timeout: int = 20) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"ok": False, "error": raw}
        return exc.code, body


def _preview(text: str, limit: int = 400) -> str:
    return str(text or "")[:limit]


def _event_types(turn: dict) -> list[str]:
    return [e.get("type") for e in (turn.get("events") or [])]


def _llm_models(turn: dict) -> list[str]:
    return [str(e.get("model") or "") for e in (turn.get("events") or []) if e.get("type") in {"llm_send", "llm"}]


def main() -> int:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_r3_5c_local_agent_ui"
    run_dir = _REPO / "runs" / "ai_tool" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    wf = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )

    observations: dict = {
        "run_id": run_id,
        "executor_claim_rule": "コード上存在する ≠ Local Agent が実際に使えた",
        "production_changes": 0,
        "experimental_changes": [
            "ai_tool/chat_interface/* UI/API",
            "tests/ai_tool/chat_interface/test_r35c_local_agent_ui.py",
        ],
        "standard_workflow_default_discovery": wf.facet_discovery,
        "cursor_connected": False,
        "stages": {},
    }

    code, health = _request("GET", "/api/health")
    observations["stages"]["ui_health"] = {
        "http": code,
        "ok": health.get("ok"),
        "executor": "cursor_http_client",
        "note": "Cursor が Chat API の health を読んだ。Local Agent の会話ではない。",
        "model": health.get("model"),
        "reachable": (health.get("models") or {}).get("reachable"),
        "ollama_models": (health.get("models") or {}).get("models"),
    }

    code, models = _request("GET", "/api/models")
    live_names = models.get("models") or []
    observations["stages"]["ollama_models"] = {
        "http": code,
        "ok": models.get("ok"),
        "reachable": models.get("reachable"),
        "models": live_names,
        "user_message": models.get("user_message"),
        "executor": "local_agent_via_chat_api",
        "note": "Chat API が起動中 Ollama のモデル一覧を取得した。",
    }

    code, created = _request("POST", "/api/session", {})
    session = created.get("session") or {}
    session_id = session.get("session_id")
    model_a = session.get("model") or models.get("default_model")
    preferred_b = ["qwen3:8b", "qwen2.5-coder:7b"]
    model_b = next((n for n in preferred_b if n in live_names and n != model_a), None)
    if not model_b:
        model_b = next((n for n in live_names if n and n != model_a), None)
    observations["stages"]["session"] = {
        "http": code,
        "session_id": session_id,
        "model_a": model_a,
        "model_b": model_b,
    }

    def chat(message: str) -> tuple[int, dict]:
        return _request("POST", "/api/chat", {"session_id": session_id, "message": message}, timeout=TIMEOUT_CHAT)

    tests = []

    # Test A
    item = {
        "id": "A",
        "name": "Chat",
        "request": "こんにちは",
        "executor": "local_agent_via_chat_api",
    }
    if not models.get("reachable"):
        item["status"] = "FAIL"
        item["reason"] = "Ollamaに接続できません"
    elif not live_names:
        item["status"] = "FAIL"
        item["reason"] = "利用可能なLLMモデルがありません"
    else:
        http, body = chat("こんにちは")
        turn = body.get("turn") or {}
        item.update(
            {
                "http": http,
                "ok": body.get("ok"),
                "is_error": body.get("is_error"),
                "model": turn.get("model") or body.get("model"),
                "answer_preview": _preview(turn.get("answer") or body.get("user_error")),
                "error": body.get("error") or turn.get("error"),
                "user_error": body.get("user_error"),
                "event_types": _event_types(turn),
                "llm_models": _llm_models(turn),
                "tool_used": turn.get("tool_used"),
                "web_search": turn.get("web_search"),
                "pipeline": turn.get("pipeline"),
            }
        )
        if body.get("ok") and turn.get("answer") and turn.get("model") == model_a:
            item["status"] = "PASS"
            item["local_agent_executed"] = True
        else:
            item["status"] = "FAIL"
            item["local_agent_executed"] = bool(turn.get("events"))
    tests.append(item)

    # Test B
    item_b = {
        "id": "B",
        "name": "Model Change",
        "executor": "local_agent_via_chat_api",
        "from_model": model_a,
        "to_model": model_b,
    }
    if not model_b:
        item_b["status"] = "FAIL"
        item_b["reason"] = "切替先モデルが無い"
    else:
        http_sw, switched = _request(
            "POST",
            "/api/session/model",
            {"session_id": session_id, "model": model_b},
        )
        item_b["switch_http"] = http_sw
        item_b["switch_ok"] = switched.get("ok")
        item_b["notice"] = switched.get("notice")
        http, body = chat("1+1は？短く答えて")
        turn = body.get("turn") or {}
        item_b.update(
            {
                "http": http,
                "ok": body.get("ok"),
                "model": turn.get("model") or body.get("model"),
                "llm_models": _llm_models(turn),
                "answer_preview": _preview(turn.get("answer") or body.get("user_error")),
                "error": body.get("error") or turn.get("error"),
                "event_types": _event_types(turn),
            }
        )
        used = (turn.get("model") == model_b) and (model_b in (item_b.get("llm_models") or [model_b]))
        if switched.get("ok") and body.get("ok") and used:
            item_b["status"] = "PASS"
            item_b["local_agent_executed"] = True
        else:
            item_b["status"] = "FAIL"
            item_b["local_agent_executed"] = bool(turn.get("events"))
    tests.append(item_b)

    # Test C — 同じセッションで履歴
    item_c = {
        "id": "C",
        "name": "Chat history",
        "executor": "local_agent_via_chat_api",
        "requests": ["この会話では合言葉をみかんにして", "合言葉は何？"],
    }
    if tests[-1].get("status") != "PASS" and tests[0].get("status") != "PASS":
        item_c["status"] = "FAIL"
        item_c["reason"] = "前段の実LLMが失敗しているため履歴を確認できない"
    else:
        http1, body1 = chat("この会話では合言葉をみかんにして")
        http2, body2 = chat("合言葉は何？")
        turn2 = body2.get("turn") or {}
        answer2 = str(turn2.get("answer") or "")
        send_events = [e for e in (turn2.get("events") or []) if e.get("type") == "llm_send"]
        history_turns = send_events[0].get("history_turns") if send_events else None
        item_c.update(
            {
                "http": [http1, http2],
                "answer1_preview": _preview((body1.get("turn") or {}).get("answer") or body1.get("user_error")),
                "answer2_preview": _preview(answer2 or body2.get("user_error")),
                "history_turns_on_second": history_turns,
                "mentions_mikan": "みかん" in answer2,
                "event_types": _event_types(turn2),
                "model": turn2.get("model"),
            }
        )
        if body2.get("ok") and history_turns and history_turns >= 1:
            item_c["status"] = "PASS"
            item_c["local_agent_executed"] = True
            if not item_c["mentions_mikan"]:
                item_c["status"] = "PARTIAL_PASS"
                item_c["note"] = "履歴は LLM に渡した。2件目の回答に合言葉が見えない。"
        else:
            item_c["status"] = "FAIL"
            item_c["local_agent_executed"] = bool(turn2.get("events"))
    tests.append(item_c)

    # Test D — Tool 選択（LLMが選ばなければ FAIL。直呼びは成功にしない）
    item_d = {
        "id": "D",
        "name": "Tool selection",
        "request": "GPUの状態を教えて",
        "executor": "local_agent_via_chat_api",
        "note": "Python から get_gpu_status を直呼びしたことは Local Agent の Tool 選択成功に数えない。",
    }
    http, body = chat("GPUの状態を教えて")
    turn = body.get("turn") or {}
    tools = [t.get("name") for t in (turn.get("tools") or [])]
    selected = [e for e in (turn.get("events") or []) if e.get("type") == "tool_select"]
    item_d.update(
        {
            "http": http,
            "ok": body.get("ok"),
            "answer_preview": _preview(turn.get("answer") or body.get("user_error")),
            "tools": tools,
            "tool_used": turn.get("tool_used"),
            "selected_by_llm": [e.get("name") for e in selected],
            "event_types": _event_types(turn),
            "model": turn.get("model"),
        }
    )
    if selected:
        item_d["status"] = "PASS"
        item_d["local_agent_executed"] = True
        item_d["local_agent_selected_tool"] = True
    else:
        item_d["status"] = "FAIL"
        item_d["local_agent_executed"] = bool(body.get("ok") or turn.get("events"))
        item_d["local_agent_selected_tool"] = False
        item_d["reason"] = "LLMがToolを選択しなかった"
    tests.append(item_d)

    # Test E — Web Search
    item_e = {
        "id": "E",
        "name": "Web Search",
        "request": "RTX 3060について最新情報を調べて",
        "executor": "local_agent_via_chat_api",
        "search_tool_exists": True,
    }
    http, body = chat("RTX 3060について最新情報を調べて")
    turn = body.get("turn") or {}
    search_events = [e for e in (turn.get("events") or []) if e.get("type") == "web_search"]
    item_e.update(
        {
            "http": http,
            "ok": body.get("ok"),
            "answer_preview": _preview(turn.get("answer") or body.get("user_error")),
            "web_search": turn.get("web_search"),
            "tools": [t.get("name") for t in (turn.get("tools") or [])],
            "search_events": search_events,
            "event_types": _event_types(turn),
            "model": turn.get("model"),
            "search_tool_exists_result": "PASS",
        }
    )
    if turn.get("web_search") and search_events:
        item_e["status"] = "PASS"
        item_e["search_executed"] = "PASS"
        item_e["local_agent_executed"] = True
    else:
        item_e["status"] = "FAIL"
        item_e["search_executed"] = "FAIL/未確認"
        item_e["local_agent_executed"] = bool(turn.get("events"))
        item_e["reason"] = "Search Tool存在 = PASS / Search実行 = FAIL/未確認"
    tests.append(item_e)

    a_ok = tests[0].get("status") == "PASS"
    b_ok = tests[1].get("status") == "PASS"
    if a_ok and b_ok:
        judgment = "PASS"
        judgment_ja = "Chat UI から Local Agent が Ollama に接続し、実LLM回答とモデル切替を確認した。"
        if tests[3].get("status") != "PASS" or tests[4].get("status") != "PASS":
            judgment = "PARTIAL_PASS"
            judgment_ja = (
                "実LLMとモデル切替はできた。Tool選択または Web Search は LLM が選ばなかった。"
            )
    elif a_ok:
        judgment = "PARTIAL_PASS"
        judgment_ja = "実LLM Chat はできた。モデル切替または後続テストが未達。"
    else:
        judgment = "FAIL"
        judgment_ja = "最低目標の実LLM Chat が確認できなかった。"

    payload = {
        **observations,
        "judgment": judgment,
        "judgment_ja": judgment_ja,
        "tests": tests,
        "browser_ui": "別途 Cursor ブラウザで確認。ここは Chat API 実測。",
    }
    (run_dir / "observations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "judgment": judgment,
                "judgment_ja": judgment_ja,
                "tests": {t["id"]: t.get("status") for t in tests},
                "production_changes": 0,
                "cursor_connected": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "judgment": judgment, "tests": payload["summary"] if False else {t["id"]: t.get("status") for t in tests}}, ensure_ascii=False, indent=2))
    print(f"wrote {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
