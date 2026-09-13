"""Local Agent Chat UI（127.0.0.1 のみ）。"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ai_tool.chat_interface.agent_turn import agent_visible_capabilities, run_chat_turn
from ai_tool.chat_interface.chat_session import (
    apply_session_model,
    empty_session,
    load_session,
    save_session,
    session_path,
    sessions_dir,
)
from ai_tool.chat_interface.dev_readonly import (
    get_report,
    get_run,
    git_snapshot,
    list_reports,
    list_runs,
    tests_snapshot,
)
from ai_tool.chat_interface.dev_cases import get_case, list_cases, session_jobs_as_notes
from ai_tool.chat_interface.activity import case_local_agent_bridge, session_activity
from ai_tool.chat_interface.dev_timeline import build_timeline, cursor_live_status
from ai_tool.chat_interface.execution_case import (
    get_case_bundle,
    link_member,
    list_case_summaries,
)
from ai_tool.chat_interface.development_job import get_job, list_jobs
from ai_tool.chat_interface.llm_errors import (
    LLM_ERROR_JA,
    MODEL_MISSING_JA,
    NO_MODELS_JA,
    OLLAMA_DOWN_JA,
    classify_llm_error,
)
from ai_tool.chat_interface.ollama_env import list_live_models
from ai_tool.chat_interface.test_batches import batch_job, public_cases, start_batch_job

STATIC_DIR = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = 8765


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _optional_id(payload: dict, key: str) -> str | None:
    """渡された ID だけ使う。無ければ生成しない。"""
    text = str(payload.get(key) or "").strip()
    return text or None


def _optional_session(sid: str) -> dict | None:
    if not sid:
        return None
    if not session_path(sid).is_file():
        return None
    return load_session(sid)


def _capabilities() -> dict:
    details = agent_visible_capabilities()
    return {
        "tools": [item["name"] for item in details],
        "tool_details": details,
        "search_web": "available",
        "note": "available は存在を示す。このターンで実行したことではない。",
    }


def _prepare_session(session: dict, live: dict | None = None) -> dict:
    live = live or list_live_models()
    if not session.get("model"):
        session["model"] = live.get("default_model") or live.get("configured_model") or ""
        save_session(session)
    return live


class ChatHandler(BaseHTTPRequestHandler):
    server_version = "LocalAgentChat/0.20"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print("[chat-ui]", self.address_string(), format % args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict) -> None:
        self._send(code, _json_bytes(payload), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def q(name: str) -> str:
            vals = qs.get(name) or []
            return str(vals[0] if vals else "").strip()

        if path in {"/", "/index.html"}:
            target = STATIC_DIR / "index.html"
            self._send(200, target.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/app.css":
            self._send(200, (STATIC_DIR / "app.css").read_bytes(), "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send(200, (STATIC_DIR / "app.js").read_bytes(), "application/javascript; charset=utf-8")
            return
        if path == "/api/matrix/search":
            from ai_tool.matrix.store import MatrixStore, search_records

            rows = search_records(
                MatrixStore().all_records(),
                q=q("q") or None,
                entity=q("entity") or None,
                attribute=q("attribute") or None,
            )
            self._send_json(
                200,
                {
                    "ok": True,
                    "llm_used": False,
                    "count": len(rows),
                    "records": rows,
                    "q": q("q") or None,
                    "entity": q("entity") or None,
                    "attribute": q("attribute") or None,
                    "note": "機械的検索。Chat 回答経路ではない。",
                },
            )
            return
        if path == "/api/matrix/last":
            from ai_tool.matrix.store import load_last_ingest

            last = load_last_ingest()
            self._send_json(
                200,
                {
                    "ok": True,
                    "ingest": last,
                    "executed": bool(last),
                    "note": "未実行なら ingest は null。MATRIX_WRITE は推測しない。",
                },
            )
            return
        if path == "/api/matrix/last_verify":
            from ai_tool.matrix.store import load_last_verify

            last = load_last_verify()
            self._send_json(
                200,
                {
                    "ok": True,
                    "verify": last,
                    "executed": bool(last),
                    "note": "未実行なら verify は null。VERIFY は推測しない。",
                },
            )
            return
        if path == "/api/matrix/last_trace":
            from ai_tool.matrix.store import load_last_trace

            last = load_last_trace()
            self._send_json(
                200,
                {
                    "ok": True,
                    "trace": last,
                    "executed": bool(last),
                    "note": "未実行なら trace は null。無い段階は推測しない。",
                },
            )
            return
        if path == "/api/matrix/last_ask":
            from ai_tool.matrix.store import load_last_ask

            last = load_last_ask()
            self._send_json(
                200,
                {
                    "ok": True,
                    "ask": last,
                    "executed": bool(last),
                    "note": "未実行なら ask は null。未実行の SEARCH / LLM は推測しない。",
                },
            )
            return
        if path == "/api/policy":
            from ai_tool.policy.loader import PolicyLoadError, load_development_policy, policy_prompt_block

            try:
                policy = load_development_policy()
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "policy": policy,
                        "prompt_block": policy_prompt_block(),
                        "llm_used": False,
                        "note": "読込。これだけでは判断を強制していない。",
                    },
                )
            except PolicyLoadError as exc:
                self._send_json(
                    200,
                    {
                        "ok": False,
                        "policy": None,
                        "error": str(exc),
                        "specification_status": "NOT_OBSERVED",
                        "note": "LOAD_FAILED。仕様完成は禁止。",
                    },
                )
            return
        if path == "/api/policy/last":
            from ai_tool.policy.paths import last_eval_path

            target = last_eval_path()
            if not target.is_file():
                self._send_json(
                    200,
                    {"ok": True, "executed": False, "evaluation": None, "note": "未実行。推測しない。"},
                )
                return
            data = json.loads(target.read_text(encoding="utf-8"))
            self._send_json(200, {"ok": True, "executed": True, "evaluation": data})
            return
        if path == "/api/spec/last":
            from ai_tool.spec_proposal.store import load_last_proposal

            last = load_last_proposal()
            self._send_json(
                200,
                {
                    "ok": True,
                    "proposal": last,
                    "executed": bool(last),
                    "note": "未実行なら proposal は null。推測しない。last は最新ポインタ。原本は JSONL。",
                },
            )
            return
        if path == "/api/spec/proposals":
            from ai_tool.spec_proposal.store import list_by_parent_proposal_id, list_by_request_id, load_jsonl

            request_id = q("request_id")
            parent_id = q("parent_proposal_id")
            if parent_id:
                rows = list_by_parent_proposal_id(parent_id)
            elif request_id:
                rows = list_by_request_id(request_id)
            else:
                rows = load_jsonl()[-20:]
            self._send_json(
                200,
                {
                    "ok": True,
                    "llm_used": False,
                    "count": len(rows),
                    "request_id": request_id or None,
                    "parent_proposal_id": parent_id or None,
                    "proposals": rows,
                    "note": "追記ログの参照。上書きしていない。Chat 通常経路ではない。",
                },
            )
            return
        if path == "/api/spec/proposal":
            from ai_tool.spec_proposal.store import get_by_proposal_id

            pid = q("proposal_id")
            if not pid:
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "found": False,
                        "executed": False,
                        "proposal": None,
                        "error": "proposal_id が空です",
                        "llm_used": False,
                        "note": "検索していない。存在しないと判定していない。",
                    },
                )
                return
            row = get_by_proposal_id(pid)
            if row is None:
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "found": False,
                        "executed": True,
                        "proposal": None,
                        "proposal_id": pid,
                        "llm_used": False,
                        "note": "JSONL に該当 proposal_id が無い。検索失敗ではない。レコードは作っていない。",
                    },
                )
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "found": True,
                    "executed": True,
                    "proposal": row,
                    "proposal_id": pid,
                    "llm_used": False,
                    "note": "JSONL 参照。上書きしていない。",
                },
            )
            return
        if path == "/api/health":
            from ai_tool.chat_interface.ollama_env import describe_ollama_env

            env = describe_ollama_env()
            live = list_live_models()
            self._send_json(
                200,
                {
                    "ok": True,
                    "executor": "local_agent",
                    "cursor_connected": False,
                    "sessions_dir": str(sessions_dir()),
                    "model": live.get("default_model") or env.get("configured_model"),
                    "ollama": env,
                    "models": live,
                    "capabilities": _capabilities(),
                },
            )
            return
        if path == "/api/models":
            live = list_live_models()
            code = 200
            payload = {
                "ok": bool(live.get("reachable")),
                "reachable": bool(live.get("reachable")),
                "models": live.get("models") or [],
                "configured_model": live.get("configured_model"),
                "default_model": live.get("default_model"),
                "error": live.get("error"),
                "user_message": live.get("user_message"),
                "capabilities": _capabilities(),
            }
            if not live.get("reachable"):
                payload["ok"] = False
                payload["error_kind"] = "ollama_down"
                payload["user_error"] = OLLAMA_DOWN_JA
            elif not (live.get("models") or []):
                payload["ok"] = False
                payload["error_kind"] = "no_models"
                payload["user_error"] = NO_MODELS_JA
            self._send_json(code, payload)
            return
        if path == "/api/execution-cases":
            self._send_json(200, list_case_summaries())
            return
        if path.startswith("/api/execution-cases/"):
            cid = unquote(path.split("/api/execution-cases/", 1)[1].strip("/"))
            result = get_case_bundle(cid)
            code = 200 if result.get("ok") else (400 if result.get("error_kind") == "invalid_id" else 404)
            if result.get("ok"):
                sid = str(result.get("session_id") or "")
                session = _optional_session(sid)
                result["timeline"] = build_timeline(session, case_id=cid)
            self._send_json(code, result)
            return
        if path == "/api/dev/cases":
            sid = q("session_id")
            session = _optional_session(sid)
            payload = list_cases(category=q("filter") or "all")
            payload["chat_jobs"] = session_jobs_as_notes(session)
            payload["local_agent_activity"] = session_activity(session)
            self._send_json(200, payload)
            return
        if path.startswith("/api/dev/cases/"):
            case_id = unquote(path.split("/api/dev/cases/", 1)[1].strip("/"))
            result = get_case(case_id)
            if result.get("ok"):
                result["local_agent_bridge"] = case_local_agent_bridge()
            code = 200 if result.get("ok") else (400 if result.get("error_kind") == "invalid_id" else 404)
            self._send_json(code, result)
            return
        if path == "/api/dev/activity":
            sid = q("session_id")
            session = _optional_session(sid)
            self._send_json(200, session_activity(session))
            return
        if path == "/api/test-cases":
            self._send_json(200, {"ok": True, "cases": public_cases(), "runs": [1, 5, 10]})
            return
        if path.startswith("/api/test-batches/"):
            job_id = unquote(path.split("/api/test-batches/", 1)[1].strip("/"))
            job = batch_job(job_id)
            self._send_json(200 if job else 404, {"ok": bool(job), "job": job})
            return
        if path == "/api/dev/events":
            sid = q("session_id")
            job_id = q("job_id") or None
            case_id = q("case_id") or None
            session = _optional_session(sid)
            self._send_json(200, build_timeline(session, job_id=job_id, case_id=case_id))
            return
        if path == "/api/dev/jobs":
            sid = q("session_id")
            session = _optional_session(sid)
            self._send_json(
                200,
                {
                    "ok": True,
                    "kind": "development",
                    "cursor_live": cursor_live_status(),
                    "jobs": list_jobs(session),
                    "note": "Session に記録した薄い Job です。Cursor ライブ状態は含みません。",
                },
            )
            return
        if path.startswith("/api/dev/jobs/"):
            job_id = unquote(path.split("/api/dev/jobs/", 1)[1].strip("/"))
            sid = q("session_id")
            session = _optional_session(sid)
            job = get_job(session, job_id)
            if job is None:
                self._send_json(404, {"ok": False, "error": "指定された Job はありません", "error_kind": "not_found"})
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "kind": "development",
                    "cursor_live": cursor_live_status(),
                    "job": job,
                    "timeline": build_timeline(session, job_id=job_id),
                },
            )
            return
        if path == "/api/dev/runs":
            self._send_json(200, list_runs())
            return
        if path.startswith("/api/dev/runs/"):
            run_id = unquote(path.split("/api/dev/runs/", 1)[1].strip("/"))
            result = get_run(run_id)
            code = 200 if result.get("ok") else (400 if result.get("error_kind") == "invalid_id" else 404)
            self._send_json(code, result)
            return
        if path == "/api/dev/reports":
            self._send_json(200, list_reports())
            return
        if path.startswith("/api/dev/reports/"):
            name = unquote(path.split("/api/dev/reports/", 1)[1].strip("/"))
            result = get_report(name)
            code = 200 if result.get("ok") else (400 if result.get("error_kind") == "invalid_id" else 404)
            self._send_json(code, result)
            return
        if path == "/api/dev/git":
            result = git_snapshot()
            code = 200 if result.get("ok") else 500
            self._send_json(code, result)
            return
        if path == "/api/dev/tests":
            self._send_json(200, tests_snapshot())
            return
        if path.startswith("/api/session/"):
            sid = path.split("/api/session/", 1)[1].strip("/")
            if not sid or sid == "model":
                self._send_json(400, {"ok": False, "error": "session_id が空です"})
                return
            session = load_session(sid)
            live = _prepare_session(session)
            self._send_json(
                200,
                {
                    "ok": True,
                    "session": session,
                    "models": live,
                    "capabilities": _capabilities(),
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "JSON を読めません"})
            return
        if parsed.path == "/api/matrix/ingest":
            from ai_tool.matrix.ingest import ingest_web_to_matrix

            query = str(payload.get("query") or "").strip()
            result = ingest_web_to_matrix(query, requested_by="user")
            code = 200 if result.get("ok") else 400
            self._send_json(code, result)
            return
        if parsed.path == "/api/matrix/verify":
            from ai_tool.matrix.verify import verify_matrix_record

            record_id = str(payload.get("record_id") or "").strip()
            result = verify_matrix_record(record_id, requested_by="user")
            self._send_json(200, result)
            return
        if parsed.path == "/api/matrix/trace":
            from ai_tool.matrix.trace import trace_matrix_record

            record_id = str(payload.get("record_id") or "").strip()
            result = trace_matrix_record(record_id, requested_by="user")
            self._send_json(200, result)
            return
        if parsed.path == "/api/matrix/ask":
            from ai_tool.matrix.ask import ask_matrix

            question = str(payload.get("question") or "").strip()
            fallback = bool(payload.get("fallback"))
            use_llm = bool(payload.get("use_llm"))
            chat_fn = None
            model = str(payload.get("model") or "").strip() or None
            if use_llm:
                from tools.system.llm import chat as ollama_chat

                chat_fn = ollama_chat
            result = ask_matrix(
                question,
                fallback=fallback,
                use_llm=use_llm,
                chat_fn=chat_fn,
                model=model,
                requested_by="user",
            )
            self._send_json(200, result)
            return
        if parsed.path == "/api/execution-cases/link":
            result = link_member(
                str(payload.get("case_id") or ""),
                str(payload.get("kind") or ""),
                str(payload.get("member_id") or payload.get("id") or ""),
            )
            code = 200 if result.get("ok") else (404 if result.get("error_kind") == "not_found" else 400)
            self._send_json(code, result)
            return
        if parsed.path == "/api/spec/propose":
            from tools.system.config import get_llm_profile
            from tools.system.llm import chat as ollama_chat
            from ai_tool.spec_proposal.propose import propose_specification

            request = str(payload.get("request") or payload.get("message") or "").strip()
            model = str(payload.get("model") or "").strip() or str(get_llm_profile().get("model") or "")
            source = str(payload.get("source") or "api").strip() or "api"
            if source not in {"api", "chat_tool_creation", "chat_development"}:
                source = "api"
            result = propose_specification(
                request,
                chat_fn=ollama_chat,
                model=model,
                source=source,
                requested_by="user",
                session_id=_optional_id(payload, "session_id"),
                development_job_id=_optional_id(payload, "development_job_id"),
                implementation_id=_optional_id(payload, "implementation_id"),
                test_run_id=_optional_id(payload, "test_run_id"),
                case_id=_optional_id(payload, "case_id"),
            )
            self._send_json(200 if result.get("ok") or result.get("saved") else 400, result)
            return
        if parsed.path == "/api/spec/revise":
            from ai_tool.spec_proposal.follow import append_human_revision

            body = payload.get("body") if isinstance(payload.get("body"), dict) else None
            result = append_human_revision(
                parent_proposal_id=str(payload.get("parent_proposal_id") or ""),
                revision_reason=str(payload.get("revision_reason") or ""),
                request=payload.get("request"),
                body=body,
                requested_by="user",
                session_id=str(payload.get("session_id") or "") or None,
                development_job_id=str(payload.get("development_job_id") or "") or None,
                implementation_id=str(payload.get("implementation_id") or "") or None,
                test_run_id=str(payload.get("test_run_id") or "") or None,
                case_id=str(payload.get("case_id") or "") or None,
                source="api",
            )
            self._send_json(200 if result.get("ok") or result.get("saved") else 400, result)
            return
        if parsed.path == "/api/spec/problem":
            from ai_tool.spec_proposal.follow import append_problem_record

            result = append_problem_record(
                parent_proposal_id=str(payload.get("parent_proposal_id") or ""),
                problem=str(payload.get("problem") or ""),
                cause=str(payload.get("cause") or ""),
                cause_status=str(payload.get("cause_status") or "NOT_DETERMINED"),
                human_correction=str(payload.get("human_correction") or ""),
                revision_reason=str(payload.get("revision_reason") or ""),
                impact=str(payload.get("impact") or ""),
                recurrence_prevention=str(payload.get("recurrence_prevention") or ""),
                requested_by="user",
                session_id=str(payload.get("session_id") or "") or None,
                development_job_id=str(payload.get("development_job_id") or "") or None,
                implementation_id=str(payload.get("implementation_id") or "") or None,
                test_run_id=str(payload.get("test_run_id") or "") or None,
                case_id=str(payload.get("case_id") or "") or None,
                source="api",
            )
            self._send_json(200 if result.get("ok") or result.get("saved") else 400, result)
            return
        if parsed.path == "/api/policy/evaluate":
            from ai_tool.policy.evaluate import evaluate_development_work

            result = evaluate_development_work(
                items=payload.get("items") if isinstance(payload.get("items"), list) else [],
                tests_passed=payload.get("tests_passed") if "tests_passed" in payload else None,
                claim_specification_complete=bool(payload.get("claim_specification_complete")),
                save=True,
            )
            self._send_json(200, result)
            return
        if parsed.path == "/api/session":
            live = list_live_models()
            data = empty_session()
            data["model"] = live.get("default_model") or live.get("configured_model") or ""
            save_session(data)
            self._send_json(
                200,
                {
                    "ok": True,
                    "session": data,
                    "models": live,
                    "capabilities": _capabilities(),
                },
            )
            return
        if parsed.path == "/api/test-batches":
            try:
                job = start_batch_job(
                    str(payload.get("test_case_id") or "") or None,
                    int(payload.get("runs") or 0),
                    model=str(payload.get("model") or "") or None,
                    prompt=str(payload.get("prompt") or "") or None,
                )
            except (KeyError, ValueError) as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            except RuntimeError as exc:
                self._send_json(409, {"ok": False, "error": str(exc)})
                return
            self._send_json(202, {"ok": True, "job": job})
            return
        if parsed.path == "/api/session/model":
            sid = str(payload.get("session_id") or "").strip()
            model = str(payload.get("model") or "").strip()
            if not sid:
                self._send_json(400, {"ok": False, "error": "session_id が空です"})
                return
            if not model:
                self._send_json(400, {"ok": False, "error": "model が空です"})
                return
            session = load_session(sid)
            result = apply_session_model(session, model)
            code = 200 if result.get("ok") else 400
            self._send_json(code, result)
            return
        if parsed.path == "/api/chat":
            from tools.system.model_registry import resolve_provider_model_name

            message = str(payload.get("message") or "").strip()
            if not message:
                self._send_json(400, {"ok": False, "error": "message が空です"})
                return
            sid = str(payload.get("session_id") or "").strip()
            session = load_session(sid) if sid else empty_session()
            live = _prepare_session(session)
            if not live.get("reachable"):
                self._send_json(
                    503,
                    {
                        "ok": False,
                        "is_error": True,
                        "error_kind": "ollama_down",
                        "user_error": OLLAMA_DOWN_JA,
                        "error": live.get("error") or "Ollama unreachable",
                        "session_id": session.get("session_id"),
                        "model": session.get("model"),
                    },
                )
                return
            current_model = resolve_provider_model_name(session.get("model"))
            session["model"] = current_model
            if not (live.get("models") or []):
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "is_error": True,
                        "error_kind": "no_models",
                        "user_error": NO_MODELS_JA,
                        "session_id": session.get("session_id"),
                    },
                )
                return
            if current_model and current_model not in (live.get("models") or []):
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "is_error": True,
                        "error_kind": "model_missing",
                        "user_error": MODEL_MISSING_JA,
                        "error": f"model not in ollama list: {current_model}",
                        "session_id": session.get("session_id"),
                        "model": current_model,
                    },
                )
                return
            if not sid:
                save_session(session)
            try:
                result = run_chat_turn(
                    session,
                    message,
                    model=current_model or None,
                    local_review_enabled=True,
                )
            except Exception as exc:  # noqa: BLE001
                classified = classify_llm_error(exc)
                self._send_json(
                    500,
                    {
                        "ok": False,
                        "is_error": True,
                        "error_kind": classified["kind"],
                        "user_error": classified["user_message"] or LLM_ERROR_JA,
                        "error": f"{type(exc).__name__}: {exc}",
                        "session_id": session.get("session_id"),
                        "model": session.get("model"),
                    },
                )
                return
            self._send_json(
                200,
                {
                    "ok": not bool(result.get("is_error")),
                    "is_error": bool(result.get("is_error")),
                    "error_kind": result.get("error_kind"),
                    "user_error": result.get("user_error"),
                    "error": result.get("error"),
                    "session_id": session["session_id"],
                    "model": result.get("model") or session.get("model"),
                    "turn": result,
                    "session": session,
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "not found"})


def serve(host: str = HOST, port: int = PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), ChatHandler)
    print(f"Local Agent Chat: http://{host}:{port}/")
    print("Cursor には接続していません。実行主体は Local Agent です。")
    httpd.serve_forever()
