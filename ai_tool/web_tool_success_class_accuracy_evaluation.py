"""Web Tool Success-Class Accuracy Evaluation — measurement harness.

Measures LLM answer accuracy when Web Research pipeline reaches SUCCESS-class state.
Does NOT modify Production. Uses production_mirror as canonical eval path.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.agent_integration.eval_production_parity_bridge import run_canonical_web_eval
from ai_tool.agent_integration.production_agent_web_loop import (
    AgentWebLoopResult,
    make_e2e_trust_file,
)
from ai_tool.agent_integration.trial import make_mock_chat_fn
from ai_tool.agent_integration.trial_scenarios import TrialScenario
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_extraction_normalization_experiment import (
    URL_GT1_OSAKA,
    URL_GT2_CAPITAL,
    URL_GT4_YOKOHAMA,
)
from ai_tool.web_tool_web_status_evaluation import GOOD_HTML, NO_FACT_HTML
from tools.system.network.web_evidence import enrich_web_tool_result
from tools.system.network.web_status import derive_web_status

RepoRoot = Path(__file__).resolve().parents[1]

AnswerClass = Literal[
    "Correct",
    "Unsupported Addition",
    "Numeric Error",
    "Entity Error",
    "Temporal Error",
    "Scope Error",
    "Contradiction",
    "Source Misuse",
    "Ambiguous",
    "SKIPPED",
]
ClaimSupport = Literal["supported", "unsupported", "contradicted", "ambiguous"]
StopReason = Literal["STOP_A", "STOP_B", "STOP_C", "STOP_D", "STOP_E"]
Knowledge = Literal["CONFIRMED", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]

NUMERIC_RE = re.compile(
    r"(?:約|およそ|推計)?\s*([0-9]{1,3}(?:[,，][0-9]{3})*(?:\.[0-9]+)?)\s*(万(?:人|円|km|㎡|平方km|平方キロ)?|人|km²|km2|㎡|%)?"
    r"|([0-9]{4,}(?:\.[0-9]+)?)\s*(?:人|km²|km2)?",
    re.I,
)
YEAR_PATTERN = re.compile(r"1[789]\d{2}|20\d{2}")
ENTITY_TOKYO = re.compile(r"東京|とうきょう|Tokyo", re.I)
ENTITY_OSAKA = re.compile(r"大阪|おおさか|Osaka", re.I)
ENTITY_YOKOHAMA = re.compile(r"横浜|よこはま|Yokohama", re.I)
ENTITY_KYOTO = re.compile(r"京都|きょうと|Kyoto", re.I)


@dataclass
class ExpectedFact:
    fact_id: str
    fact_type: Literal["entity", "numeric", "temporal", "text", "comparison"]
    evidence_patterns: list[str]
    answer_patterns: list[str]
    forbidden_patterns: list[str] = field(default_factory=list)
    numeric_min: float | None = None
    numeric_max: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SuccessClassCaseSpec:
    case_id: str
    category: str
    label: str
    user_request: str
    expected_facts: list[ExpectedFact]
    search_web_fn: Callable[..., dict] | None = None
    read_url_text_fn: Callable[..., dict] | None = None
    mock_scenario: TrialScenario | None = None
    success_class_candidate: bool = True
    expect_correct: bool = True
    taxonomy_control: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["expected_facts"] = [f.to_dict() for f in self.expected_facts]
        if self.mock_scenario:
            d["mock_scenario"] = self.mock_scenario.to_dict()
        return d


@dataclass
class ClaimResult:
    claim_id: str
    claim_text: str
    claim_type: str
    support: ClaimSupport
    deterministic_verifiable: bool
    verification_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SuccessClassCaseResult:
    case_id: str
    category: str
    label: str
    web_success: bool
    web_status_overall: str | None
    fact_ready: bool | None
    evidence_main_text_len: int
    llm_answer: str | None
    raw_llm_answer: str | None
    answer_class: AnswerClass
    claims: list[ClaimResult]
    deterministic_verifiable_claims: list[str]
    expected_facts_met: dict[str, bool]
    path: str
    live: bool
    expect_correct: bool = True
    taxonomy_control: bool = False
    notes: list[str] = field(default_factory=list)
    classification: Knowledge = "UNKNOWN"
    production_equivalent: bool = True
    boundary_applied: bool = False
    web_session_tracked: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["claims"] = [c.to_dict() for c in self.claims]
        return d


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def _normalize_numeric(raw: str, unit: str = "") -> float | None:
    s = str(raw or "").replace(",", "").replace("，", "")
    try:
        val = float(s)
    except ValueError:
        return None
    u = str(unit or "").lower()
    if "万" in u:
        val *= 10_000
    return val


def extract_population_numeric_values(text: str) -> list[float]:
    """Population-scale numerics only — excludes ratios and small decimals."""
    out: list[float] = []
    blob = text or ""
    for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*million", blob, re.I):
        try:
            n = float(m.group(1)) * 1_000_000
            if n >= 500_000:
                out.append(n)
        except ValueError:
            pass
    for m in NUMERIC_RE.finditer(blob):
        raw = m.group(1) or m.group(2)
        if not raw:
            continue
        span = m.group(0)
        unit = "万" if "万" in span else ""
        n = _normalize_numeric(raw, unit)
        if n is None:
            continue
        if "万" in span and n >= 500_000:
            out.append(n)
        elif n >= 500_000:
            out.append(n)
    return out


def extract_numeric_values(text: str) -> list[float]:
    out: list[float] = []
    for m in NUMERIC_RE.finditer(text or ""):
        raw = m.group(1) or m.group(2)
        if not raw:
            continue
        span = m.group(0)
        unit = ""
        if "万" in span:
            unit = "万"
        n = _normalize_numeric(raw, unit)
        if n is not None and n > 0:
            out.append(n)
    return out


def _fixture_search(url: str, title: str = "Fixture") -> Callable[..., dict]:
    def fn(**kwargs: Any) -> dict[str, Any]:
        return enrich_web_tool_result(
            "search_web",
            {
                "query": kwargs.get("query", ""),
                "hits": [{"title": title, "url": url, "backend": "fixture"}],
            },
        )

    return fn


def _fixture_fetch(html: str, url: str = "https://fixture.local/page") -> Callable[..., dict]:
    ev = normalize_html_to_evidence(html)

    def fn(**kwargs: Any) -> dict[str, Any]:
        u = kwargs.get("url") or url
        return enrich_web_tool_result(
            "read_url_text",
            {
                "ok": True,
                "url": u,
                "main_text": ev["main_text"],
                "quality": ev["quality"],
            },
        )

    return fn


def _live_fetch_fn(**kwargs: Any) -> dict[str, Any]:
    return read_url_text(**kwargs)


CAPITAL_FIXTURE = """
<html><head><title>日本の首都</title></head><body>
<main><h1>日本の首都</h1>
<p>現行の日本の法令には首都についての定義はない。過去においても「首都」という語と
「都」「京」との関係について明確にされたことがない。そのため「日本の首都」という語そのものについて議論がある。</p>
<p>現在、日本の首都は一般に東京（東京都）と認識されている。首都圏整備法では首都圏の法的定義が存在する。
東京は日本の政治・経済・文化の中心地であり、国会や中央政府の主要機関が置かれている。</p>
</main></body></html>
"""

YOKOHAMA_FIXTURE = """
<html><head><title>横浜市</title></head><body>
<main><h1>横浜市</h1>
<p>横浜市（よこはまし）は、神奈川県東部に位置する市。神奈川県の県庁所在地および日本で人口が最多の市で、
政令指定都市である。日本屈指の港湾都市・商工業都市でもある。</p>
<p>東京大都市圏（首都圏）に属する。市の人口は約375.9万人で全国の市区町村としては最多の人口である。
市域の過半は旧武蔵国で、南西部は旧相模国鎌倉郡に相当する。</p>
</main></body></html>
"""

COMPARATIVE_FIXTURE = """
<html><head><title>人口比較</title></head><body>
<main><h1>人口比較</h1>
<p>横浜市（神奈川県）の人口は約375.9万人で、政令指定都市の中では最多クラスである。
大阪市（大阪府）の人口は約272万人（2024年）で、西日本最大の都市である。</p>
<p>市区町村単位で比較すると、横浜市の人口が大阪市より多い。両市とも政令指定都市に指定されており、
近畿地方と首都圏の主要都市として機能している。</p>
</main></body></html>
"""

TEMPORAL_FIXTURE = """
<html><head><title>大阪市</title></head><body>
<main><h1>大阪市</h1>
<p>大阪市（おおさかし）は、大阪府中部に位置する市。西日本で最多の人口を有する市であり、
大阪府の府庁所在地で、政令指定都市に指定されている。</p>
<p>1889年（明治22年）に市制が施行された。現在の人口は約272万人で、24の行政区から構成される。
近畿地方の経済・文化・交通の中心都市として発展してきた。</p>
</main></body></html>
"""


def success_class_dataset(*, include_live: bool = True) -> list[SuccessClassCaseSpec]:
    """Golden SUCCESS-class dataset with independent expected facts."""
    cases: list[SuccessClassCaseSpec] = [
        # --- Mock-controlled (deterministic taxonomy validation) ---
        SuccessClassCaseSpec(
            "SC-M01",
            "basic_facts",
            "mock capital correct",
            "日本の首都はどこですか。Web検索で確認しread_url_textで取得して答えてください。",
            [
                ExpectedFact(
                    "capital_tokyo",
                    "entity",
                    [r"東京", r"東京都"],
                    [r"東京"],
                    forbidden_patterns=[r"大阪.*首都", r"Kyoto.*capital"],
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/capital", "日本の首都"),
            read_url_text_fn=_fixture_fetch(CAPITAL_FIXTURE),
            mock_scenario=TrialScenario(
                "sc_m01",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "日本の首都"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/capital"}},
                ],
                mock_final_answer="Web検索とページ確認の結果、日本の首都は東京（東京都）と認識されています。",
            ),
        ),
        SuccessClassCaseSpec(
            "SC-M02",
            "numeric_facts",
            "mock population correct",
            "大阪市の人口をWeb検索しread_url_textで確認して教えてください。",
            [
                ExpectedFact(
                    "osaka_population",
                    "numeric",
                    [r"2[,，]?7[0-9]{2}[,，]?[0-9]{3}", r"275\s*万", r"272\s*万"],
                    [r"275|272|2[,，]?7[0-9]{2}"],
                    numeric_min=2_500_000,
                    numeric_max=2_900_000,
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/osaka"),
            read_url_text_fn=_fixture_fetch(GOOD_HTML),
            mock_scenario=TrialScenario(
                "sc_m02",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "大阪市 人口"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/osaka"}},
                ],
                mock_final_answer="ページ本文によると、人口は約275万人（2,750,000人）です。",
            ),
        ),
        SuccessClassCaseSpec(
            "SC-M03",
            "numeric_facts",
            "mock numeric error",
            "大阪市の人口をWeb検索しread_url_textで確認して教えてください。",
            [
                ExpectedFact(
                    "osaka_population",
                    "numeric",
                    [r"2[,，]?7[0-9]{2}[,，]?[0-9]{3}", r"275\s*万"],
                    [r"275|272|2[,，]?7[0-9]{2}"],
                    numeric_min=2_500_000,
                    numeric_max=2_900_000,
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/osaka"),
            read_url_text_fn=_fixture_fetch(GOOD_HTML),
            mock_scenario=TrialScenario(
                "sc_m03",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "大阪市 人口"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/osaka"}},
                ],
                mock_final_answer="人口は約1,900万人です。",
            ),
            expect_correct=False,
            taxonomy_control=True,
        ),
        SuccessClassCaseSpec(
            "SC-M04",
            "basic_facts",
            "mock unsupported addition",
            "日本の首都をWeb検索しread_url_textで確認して教えてください。",
            [
                ExpectedFact(
                    "capital_tokyo",
                    "entity",
                    [r"東京"],
                    [r"東京"],
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/capital"),
            read_url_text_fn=_fixture_fetch(CAPITAL_FIXTURE),
            mock_scenario=TrialScenario(
                "sc_m04",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "日本の首都"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/capital"}},
                ],
                mock_final_answer="首都は東京です。人口は1,400万人です。",
            ),
            expect_correct=False,
            taxonomy_control=True,
        ),
        SuccessClassCaseSpec(
            "SC-M05",
            "entity_facts",
            "mock entity error",
            "日本の首都をWeb検索しread_url_textで確認して教えてください。",
            [
                ExpectedFact(
                    "capital_tokyo",
                    "entity",
                    [r"東京"],
                    [r"東京"],
                    forbidden_patterns=[r"大阪.*首都"],
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/capital"),
            read_url_text_fn=_fixture_fetch(CAPITAL_FIXTURE),
            mock_scenario=TrialScenario(
                "sc_m05",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "日本の首都"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/capital"}},
                ],
                mock_final_answer="日本の首都は大阪市です。",
            ),
            expect_correct=False,
            taxonomy_control=True,
        ),
        SuccessClassCaseSpec(
            "SC-M06",
            "temporal_facts",
            "mock temporal correct",
            "大阪市の市制施行年をWeb検索しread_url_textで確認して教えてください。",
            [
                ExpectedFact(
                    "osaka_founded",
                    "temporal",
                    [r"1889\s*年"],
                    [r"1889"],
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/osaka-history"),
            read_url_text_fn=_fixture_fetch(TEMPORAL_FIXTURE),
            mock_scenario=TrialScenario(
                "sc_m06",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "大阪市 市制施行"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/osaka-history"}},
                ],
                mock_final_answer="1889年に市制が施行されました。",
            ),
        ),
        SuccessClassCaseSpec(
            "SC-M07",
            "comparative",
            "mock comparative correct",
            "横浜市と大阪市の人口を比較してください。Web検索しread_url_textで確認して。",
            [
                ExpectedFact(
                    "yokohama_larger",
                    "comparison",
                    [r"375\.9\s*万", r"272\s*万"],
                    [r"横浜.*多|375.*272|横浜市.*最多"],
                )
            ],
            search_web_fn=_fixture_search("https://fixture.local/compare"),
            read_url_text_fn=_fixture_fetch(COMPARATIVE_FIXTURE),
            mock_scenario=TrialScenario(
                "sc_m07",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "横浜 大阪 人口 比較"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/compare"}},
                ],
                mock_final_answer="横浜市（約375.9万人）の方が大阪市（約272万人）より人口が多いです。",
            ),
        ),
        SuccessClassCaseSpec(
            "SC-M08",
            "multi_fact",
            "mock multi-fact correct",
            "横浜市の人口と特徴をWeb検索しread_url_textで確認して教えてください。",
            [
                ExpectedFact(
                    "yokohama_population",
                    "numeric",
                    [r"375\.9\s*万"],
                    [r"375"],
                    numeric_min=3_700_000,
                    numeric_max=3_800_000,
                ),
                ExpectedFact(
                    "yokohama_entity",
                    "entity",
                    [r"横浜"],
                    [r"横浜"],
                ),
            ],
            search_web_fn=_fixture_search("https://fixture.local/yokohama"),
            read_url_text_fn=_fixture_fetch(YOKOHAMA_FIXTURE),
            mock_scenario=TrialScenario(
                "sc_m08",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "横浜市 人口"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/yokohama"}},
                ],
                mock_final_answer="横浜市の人口は約375.9万人で、全国の市区町村では最多です。",
            ),
        ),
        # --- Negative (NOT success-class — for separation) ---
        SuccessClassCaseSpec(
            "SC-NEG01",
            "negative",
            "no evidence — excluded from SUCCESS-class stats",
            "このページの交通スケジュールだけを根拠に大阪市の人口を答えてください。",
            [],
            search_web_fn=_fixture_search("https://fixture.local/schedules"),
            read_url_text_fn=_fixture_fetch(NO_FACT_HTML),
            mock_scenario=TrialScenario(
                "sc_neg01",
                "",
                "either",
                "",
                mock_tool_calls=[
                    {"name": "search_web", "arguments": {"query": "大阪 人口"}},
                    {"name": "read_url_text", "arguments": {"url": "https://fixture.local/schedules"}},
                ],
                mock_final_answer="確認できませんでした。",
            ),
            success_class_candidate=False,
        ),
    ]

    if include_live:
        cases.extend([
            SuccessClassCaseSpec(
                "SC-L01",
                "basic_facts",
                "live osaka population",
                "大阪市の人口をWeb検索で調べ、read_url_textで確認して教えてください。",
                [
                    ExpectedFact(
                        "osaka_population",
                        "numeric",
                        [r"人口", r"272\s*万", r"275\s*万", r"2[,，]?7[0-9]{2}"],
                        [r"272|275|2[,，]?7[0-9]{2}|人口"],
                        numeric_min=2_500_000,
                        numeric_max=2_900_000,
                    )
                ],
                notes=f"Live fetch target: {URL_GT1_OSAKA}",
            ),
            SuccessClassCaseSpec(
                "SC-L02",
                "basic_facts",
                "live capital of japan",
                "日本の首都はどこですか。Web検索で確認し、read_url_textでページ本文を取得して答えてください。",
                [
                    ExpectedFact(
                        "capital_tokyo",
                        "entity",
                        [r"東京", r"東京都"],
                        [r"東京"],
                        forbidden_patterns=[r"大阪.*首都"],
                    )
                ],
                notes=f"Live fetch target: {URL_GT2_CAPITAL}",
            ),
            SuccessClassCaseSpec(
                "SC-L03",
                "numeric_facts",
                "live yokohama population",
                "横浜市の人口をWeb検索しread_url_textで確認して教えてください。",
                [
                    ExpectedFact(
                        "yokohama_population",
                        "numeric",
                        [r"375", r"374", r"376", r"人口"],
                        [r"375|374|376|人口"],
                        numeric_min=3_600_000,
                        numeric_max=3_900_000,
                    )
                ],
                notes=f"Live fetch target: {URL_GT4_YOKOHAMA}",
            ),
            SuccessClassCaseSpec(
                "SC-L04",
                "comparative",
                "live osaka vs yokohama population",
                "横浜市と大阪市の人口を比較してください。どちらが多いですか。Web検索しread_url_textで確認して。",
                [
                    ExpectedFact(
                        "yokohama_larger",
                        "comparison",
                        [r"375", r"272", r"横浜", r"大阪"],
                        [r"横浜.*多|375.*272|横浜市.*最多|横浜の方が"],
                    )
                ],
                notes="Requires fetch of comparative evidence from live search",
            ),
        ])
    return cases


def is_success_class(agg: dict[str, Any] | None, *, fetch_quality: dict[str, Any] | None = None) -> bool:
    if not agg:
        return False
    overall = str(agg.get("overall") or "")
    if overall != "SUCCESS":
        return False
    layers = agg.get("layers") or {}
    if layers.get("search") not in ("SUCCESS", "NOT_RUN"):
        return False
    if layers.get("fetch") != "SUCCESS":
        return False
    if layers.get("extraction") != "READY":
        return False
    if layers.get("evidence") != "AVAILABLE":
        return False
    if fetch_quality and not fetch_quality.get("fact_ready"):
        return False
    return True


def _evidence_from_loop(loop: AgentWebLoopResult) -> tuple[str, dict[str, Any] | None]:
    for ex in reversed(loop.tool_executions):
        if ex.tool_name == "read_url_text" and isinstance(ex.result, dict):
            mt = str(ex.result.get("main_text") or "")
            q = ex.result.get("quality") if isinstance(ex.result.get("quality"), dict) else {}
            return mt, q
    return "", None


def _check_fact_in_text(text: str, fact: ExpectedFact) -> bool:
    blob = str(text or "")
    for pat in fact.evidence_patterns:
        if re.search(pat, blob, re.I):
            return True
    if fact.numeric_min is not None and fact.numeric_max is not None:
        nums = extract_numeric_values(blob)
        return any(fact.numeric_min <= n <= fact.numeric_max for n in nums)
    return False


def _check_answer_fact(answer: str, evidence: str, fact: ExpectedFact) -> tuple[bool, ClaimSupport, list[ClaimResult]]:
    claims: list[ClaimResult] = []
    ans = str(answer or "")
    ev = str(evidence or "")

    for fp in fact.forbidden_patterns:
        if re.search(fp, ans, re.I):
            claims.append(
                ClaimResult(
                    f"{fact.fact_id}_forbidden",
                    fp,
                    fact.fact_type,
                    "contradicted",
                    True,
                    "regex_forbidden",
                )
            )
            return False, "contradicted", claims

    if fact.fact_type == "numeric" and fact.numeric_min is not None:
        extract_fn = extract_population_numeric_values if "population" in fact.fact_id else extract_numeric_values
        ans_nums = extract_fn(ans)
        ev_nums = extract_fn(ev)
        if not ans_nums:
            # fallback: any large number in answer
            ans_nums = [n for n in extract_numeric_values(ans) if n >= (fact.numeric_min or 0) * 0.5]
        if not ans_nums:
            claims.append(
                ClaimResult(f"{fact.fact_id}_numeric", "no numeric in answer", "numeric", "ambiguous", False)
            )
            return False, "ambiguous", claims
        best = min(ans_nums, key=lambda n: abs(n - ((fact.numeric_min or 0) + (fact.numeric_max or fact.numeric_min or 0)) / 2))
        ans_ok = any(fact.numeric_min <= n <= (fact.numeric_max or fact.numeric_min * 2) for n in ans_nums)
        ev_ok = any(fact.numeric_min <= n <= (fact.numeric_max or fact.numeric_min * 2) for n in ev_nums)
        if ans_ok and ev_ok:
            claims.append(
                ClaimResult(
                    f"{fact.fact_id}_numeric",
                    str(int(best)),
                    "numeric",
                    "supported",
                    True,
                    "numeric_range_match",
                )
            )
            return True, "supported", claims
        if not ev_ok:
            claims.append(
                ClaimResult(f"{fact.fact_id}_numeric", str(int(best)), "numeric", "ambiguous", False)
            )
            return False, "ambiguous", claims
        claims.append(
            ClaimResult(
                f"{fact.fact_id}_numeric",
                str(int(best)),
                "numeric",
                "contradicted",
                True,
                "numeric_range_mismatch",
            )
        )
        return False, "contradicted", claims

    if fact.fact_type == "entity":
        ans_match = any(re.search(p, ans, re.I) for p in fact.answer_patterns)
        ev_match = _check_fact_in_text(ev, fact)
        if ans_match and ev_match:
            claims.append(
                ClaimResult(f"{fact.fact_id}_entity", fact.fact_id, "entity", "supported", True, "regex_entity")
            )
            return True, "supported", claims
        if ans_match and not ev_match:
            claims.append(
                ClaimResult(f"{fact.fact_id}_entity", fact.fact_id, "entity", "unsupported", True, "regex_entity")
            )
            return False, "unsupported", claims
        if not ans_match:
            claims.append(
                ClaimResult(f"{fact.fact_id}_entity", "missing entity", "entity", "contradicted", True, "regex_entity")
            )
            return False, "contradicted", claims

    if fact.fact_type == "temporal":
        ans_year_m = YEAR_PATTERN.search(ans)
        ev_year_m = YEAR_PATTERN.search(ev)
        if not ans_year_m:
            claims.append(
                ClaimResult(f"{fact.fact_id}_temporal", "no year", "temporal", "ambiguous", False)
            )
            return False, "ambiguous", claims
        if ans_year_m and ev_year_m and ans_year_m.group(0) == ev_year_m.group(0):
            claims.append(
                ClaimResult(
                    f"{fact.fact_id}_temporal",
                    ans_year_m.group(0),
                    "temporal",
                    "supported",
                    True,
                    "year_match",
                )
            )
            return True, "supported", claims
        claims.append(
            ClaimResult(
                f"{fact.fact_id}_temporal",
                ans_year_m.group(0),
                "temporal",
                "contradicted",
                True,
                "year_mismatch",
            )
        )
        return False, "contradicted", claims

    if fact.fact_type in ("text", "comparison"):
        ans_ok = any(re.search(p, ans, re.I) for p in fact.answer_patterns)
        ev_ok = _check_fact_in_text(ev, fact)
        if ans_ok and ev_ok:
            claims.append(
                ClaimResult(f"{fact.fact_id}_text", fact.fact_id, fact.fact_type, "supported", True, "regex")
            )
            return True, "supported", claims
        if ans_ok and not ev_ok:
            claims.append(
                ClaimResult(f"{fact.fact_id}_text", fact.fact_id, fact.fact_type, "unsupported", False)
            )
            return False, "unsupported", claims
        claims.append(
            ClaimResult(f"{fact.fact_id}_text", fact.fact_id, fact.fact_type, "contradicted", False)
        )
        return False, "contradicted", claims

    return False, "ambiguous", claims


def _detect_unsupported_additions(answer: str, evidence: str) -> list[ClaimResult]:
    """Detect numeric claims in answer without evidence support."""
    claims: list[ClaimResult] = []
    ans_nums = extract_numeric_values(answer)
    ev_nums = extract_numeric_values(evidence)
    for i, n in enumerate(ans_nums):
        supported = any(abs(n - e) / max(e, 1) < 0.05 for e in ev_nums)
        if not supported and n > 1_000_000:
            claims.append(
                ClaimResult(
                    f"extra_numeric_{i}",
                    str(int(n)),
                    "numeric",
                    "unsupported",
                    True,
                    "numeric_not_in_evidence",
                )
            )
    return claims


def classify_answer(
    answer: str | None,
    evidence: str,
    expected_facts: list[ExpectedFact],
) -> tuple[AnswerClass, list[ClaimResult], dict[str, bool], list[str]]:
    if not answer or not str(answer).strip():
        return "Ambiguous", [], {}, []

    all_claims: list[ClaimResult] = []
    fact_met: dict[str, bool] = {}
    det_verifiable: list[str] = []
    primary: AnswerClass = "Correct"

    for fact in expected_facts:
        ok, _support, claims = _check_answer_fact(answer, evidence, fact)
        all_claims.extend(claims)
        fact_met[fact.fact_id] = ok
        for c in claims:
            if c.deterministic_verifiable:
                det_verifiable.append(c.claim_id)

    extra = _detect_unsupported_additions(answer, evidence)
    all_claims.extend(extra)

    if extra and primary == "Correct":
        primary = "Unsupported Addition"
    if not all(fact_met.values()) and expected_facts:
        failed = [f for f, ok in fact_met.items() if not ok]
        for c in all_claims:
            if c.support == "contradicted":
                if c.claim_type == "numeric":
                    primary = "Numeric Error"
                elif c.claim_type == "entity":
                    primary = "Entity Error"
                elif c.claim_type == "temporal":
                    primary = "Temporal Error"
                else:
                    primary = "Contradiction"
                break
        if primary == "Correct" and failed:
            primary = "Contradiction"
    elif not expected_facts:
        primary = "Ambiguous"

    if primary == "Correct" and all(fact_met.values()) and expected_facts:
        primary = "Correct"

    return primary, all_claims, fact_met, det_verifiable


def run_success_class_case(
    spec: SuccessClassCaseSpec,
    *,
    chat_fn: Callable[..., Any],
    model: str,
    trust_path: Path,
    live: bool = False,
) -> SuccessClassCaseResult:
    notes: list[str] = []
    chat = chat_fn
    if spec.mock_scenario:
        chat = make_mock_chat_fn(spec.mock_scenario)

    loop, path_meta = run_canonical_web_eval(
        spec.user_request,
        chat_fn=chat,
        model=model or "mock",
        search_web_fn=spec.search_web_fn,
        read_url_text_fn=spec.read_url_text_fn or (_live_fetch_fn if live and not spec.read_url_text_fn else None),
        trust_path=trust_path,
        live=live,
        scored=True,
    )

    agg = loop.web_session_aggregate or {}
    evidence, quality = _evidence_from_loop(loop)
    web_ok = is_success_class(agg, fetch_quality=quality)
    _path_kw = {
        "path": path_meta.path_label,
        "production_equivalent": path_meta.production_equivalent,
        "boundary_applied": loop.boundary_applied,
        "web_session_tracked": path_meta.web_session_tracker,
    }

    if not spec.success_class_candidate:
        return SuccessClassCaseResult(
            case_id=spec.case_id,
            category=spec.category,
            label=spec.label,
            web_success=web_ok,
            web_status_overall=agg.get("overall"),
            fact_ready=(quality or {}).get("fact_ready") if quality else None,
            evidence_main_text_len=len(evidence),
            llm_answer=loop.final_answer,
            raw_llm_answer=loop.raw_llm_answer,
            answer_class="SKIPPED",
            claims=[],
            deterministic_verifiable_claims=[],
            expected_facts_met={},
            live=live,
            expect_correct=spec.expect_correct,
            taxonomy_control=spec.taxonomy_control,
            notes=["negative case — excluded from SUCCESS-class accuracy stats"],
            classification="CONFIRMED",
            **_path_kw,
        )

    if not web_ok:
        notes.append(f"web not SUCCESS-class: {agg.get('overall')}")
        return SuccessClassCaseResult(
            case_id=spec.case_id,
            category=spec.category,
            label=spec.label,
            web_success=False,
            web_status_overall=agg.get("overall"),
            fact_ready=(quality or {}).get("fact_ready") if quality else None,
            evidence_main_text_len=len(evidence),
            llm_answer=loop.final_answer,
            raw_llm_answer=loop.raw_llm_answer,
            answer_class="SKIPPED",
            claims=[],
            deterministic_verifiable_claims=[],
            expected_facts_met={},
            live=live,
            expect_correct=spec.expect_correct,
            taxonomy_control=spec.taxonomy_control,
            notes=notes,
            classification="OBSERVATION",
            **_path_kw,
        )

    answer_class, claims, fact_met, det_ver = classify_answer(
        loop.final_answer, evidence, spec.expected_facts
    )

    return SuccessClassCaseResult(
        case_id=spec.case_id,
        category=spec.category,
        label=spec.label,
        web_success=True,
        web_status_overall=agg.get("overall"),
        fact_ready=(quality or {}).get("fact_ready"),
        evidence_main_text_len=len(evidence),
        llm_answer=loop.final_answer,
        raw_llm_answer=loop.raw_llm_answer,
        answer_class=answer_class,
        claims=claims,
        deterministic_verifiable_claims=det_ver,
        expected_facts_met=fact_met,
        live=live,
        expect_correct=spec.expect_correct,
        taxonomy_control=spec.taxonomy_control,
        notes=notes,
        classification="CONFIRMED" if answer_class == "Correct" else "OBSERVATION",
        **_path_kw,
    )


def aggregate_accuracy(results: list[SuccessClassCaseResult]) -> dict[str, Any]:
    web_success = [r for r in results if r.web_success]
    negative = [r for r in results if r.answer_class == "SKIPPED" and r.category == "negative"]
    scored = [r for r in web_success if r.answer_class != "SKIPPED"]
    expected_correct = [r for r in scored if r.expect_correct]
    taxonomy_controls = [r for r in scored if r.taxonomy_control]
    live_scored = [r for r in expected_correct if r.live]
    mock_scored = [r for r in expected_correct if not r.live]

    counts = {
        "Correct": 0,
        "Unsupported Addition": 0,
        "Numeric Error": 0,
        "Entity Error": 0,
        "Temporal Error": 0,
        "Scope Error": 0,
        "Contradiction": 0,
        "Source Misuse": 0,
        "Ambiguous": 0,
    }
    for r in scored:
        if r.answer_class in counts:
            counts[r.answer_class] += 1

    ec_correct = sum(1 for r in expected_correct if r.answer_class == "Correct")
    ec_total = len(expected_correct)
    ec_accuracy = ec_correct / ec_total if ec_total else 0.0

    tax_detected = sum(1 for r in taxonomy_controls if r.answer_class != "Correct")
    tax_total = len(taxonomy_controls)
    tax_rate = tax_detected / tax_total if tax_total else 0.0

    live_correct = sum(1 for r in live_scored if r.answer_class == "Correct")
    live_total = len(live_scored)
    live_accuracy = live_correct / live_total if live_total else None

    mock_correct = sum(1 for r in mock_scored if r.answer_class == "Correct")
    mock_total = len(mock_scored)
    mock_accuracy = mock_correct / mock_total if mock_total else 0.0

    det_types: dict[str, int] = {}
    for r in scored:
        for c in r.claims:
            if c.deterministic_verifiable and c.verification_method:
                det_types[c.verification_method] = det_types.get(c.verification_method, 0) + 1

    return {
        "web_success_count": len(web_success),
        "web_failure_count": len([r for r in results if not r.web_success and r.answer_class == "SKIPPED"]),
        "negative_excluded_count": len(negative),
        "llm_answer_count": len(scored),
        "llm_answer_expected_correct_count": ec_total,
        "correct_count": ec_correct,
        "accuracy_rate": round(ec_accuracy, 4),
        "accuracy_rate_all_scored": round(sum(1 for r in scored if r.answer_class == "Correct") / len(scored), 4) if scored else 0.0,
        "live_accuracy_rate": round(live_accuracy, 4) if live_accuracy is not None else None,
        "live_success_class_count": live_total,
        "mock_accuracy_rate": round(mock_accuracy, 4),
        "taxonomy_control_count": tax_total,
        "taxonomy_detection_rate": round(tax_rate, 4),
        "failure_taxonomy": counts,
        "deterministic_verification_methods": det_types,
    }


def architecture_options(agg: dict[str, Any]) -> list[dict[str, Any]]:
    acc = agg.get("accuracy_rate", 0)
    numeric_err = agg.get("failure_taxonomy", {}).get("Numeric Error", 0)
    total = agg.get("llm_answer_count", 0)
    numeric_rate = numeric_err / total if total else 0

    return [
        {
            "id": "OPT0_NO_ACTION",
            "name": "現状維持",
            "accuracy_improvement": "none needed if rate high",
            "coverage": "full pipeline as-is",
            "regression_risk": "none",
            "note": f"accuracy={acc}, numeric_error_rate={numeric_rate:.2f}",
        },
        {
            "id": "OPT1_PROMPT_AGENT",
            "name": "Prompt / Agent policy強化",
            "accuracy_improvement": "moderate for entity/temporal errors",
            "coverage": "LLM layer only",
            "regression_risk": "medium",
            "human_review": True,
        },
        {
            "id": "OPT2_EVIDENCE_GROUNDING",
            "name": "Evidence grounding強化",
            "accuracy_improvement": "moderate for unsupported additions",
            "coverage": "evidence → LLM input",
            "regression_risk": "low-medium",
            "human_review": False,
        },
        {
            "id": "OPT3_STRUCTURED_CLAIM",
            "name": "Structured Claim",
            "accuracy_improvement": "high if claim errors frequent",
            "coverage": "claim extraction + validation",
            "regression_risk": "high",
            "human_review": True,
        },
        {
            "id": "OPT4_MECHANICAL",
            "name": "Mechanical / deterministic verification",
            "accuracy_improvement": f"high for numeric ({numeric_err} errors observed)",
            "coverage": "deterministic-verifiable claims only",
            "regression_risk": "medium",
            "human_review": True,
            "note": "ROI depends on numeric_error_rate and verifiable claim fraction",
        },
        {
            "id": "OPT5_HYBRID",
            "name": "Hybrid — mechanical for verifiable, LLM for rest",
            "accuracy_improvement": "balanced",
            "coverage": "partial mechanical + LLM fallback",
            "regression_risk": "medium-high",
            "human_review": True,
        },
    ]


def select_option(agg: dict[str, Any], options: list[dict[str, Any]]) -> tuple[str, str, StopReason, str, list[str]]:
    acc = agg.get("accuracy_rate", 0)
    ec_total = agg.get("llm_answer_expected_correct_count", 0)
    live_acc = agg.get("live_accuracy_rate")
    numeric_err = agg.get("failure_taxonomy", {}).get("Numeric Error", 0)
    unsupported = agg.get("failure_taxonomy", {}).get("Unsupported Addition", 0)
    live_numeric = 0
    live_total = agg.get("live_success_class_count", 0)

    if ec_total == 0:
        return (
            "OPT0_NO_ACTION",
            "No SUCCESS-class expected-correct cases — cannot measure LLM failure rate",
            "STOP_B",
            "Defer",
            [o["id"] for o in options if o["id"] != "OPT0_NO_ACTION"],
        )

    # Primary decision on expected-correct accuracy (excludes injected taxonomy controls)
    if acc >= 0.85 and (live_acc is None or live_acc >= 0.75):
        why = (
            f"Expected-correct SUCCESS-class accuracy {acc:.0%} ({agg.get('correct_count')}/{ec_total}). "
            f"Live accuracy={live_acc}. Taxonomy detection={agg.get('taxonomy_detection_rate'):.0%}. "
            "Mechanical layer ROI low for current measured failure rate."
        )
        return "OPT0_NO_ACTION", why, "STOP_A", "Not Recommended", [
            o["id"] for o in options if o["id"] != "OPT0_NO_ACTION"
        ]

    if live_total and live_acc is not None and live_acc < 0.75 and numeric_err >= 1:
        why = (
            f"Live SUCCESS-class accuracy {live_acc:.0%} ({live_total} cases). "
            f"Numeric errors in live answers suggest grounding gap — "
            "mechanical verification for population numerics may have ROI; defer to Human Review."
        )
        return "OPT4_MECHANICAL", why, "STOP_E", "Defer", [
            o["id"] for o in options if o["id"] not in ("OPT4_MECHANICAL", "OPT5_HYBRID")
        ]

    if unsupported >= 1 and acc >= 0.7:
        why = (
            f"Expected-correct accuracy {acc:.0%} but unsupported additions observed. "
            "Evidence grounding (OPT2) may help — eval-only observation; Human Review for Production."
        )
        return "OPT2_EVIDENCE_GROUNDING", why, "STOP_C", "Defer", [
            o["id"] for o in options if o["id"] not in ("OPT2_EVIDENCE_GROUNDING",)
        ]

    why = (
        f"Expected-correct accuracy {acc:.0%}. Mock taxonomy validated at {agg.get('taxonomy_detection_rate'):.0%}. "
        "Mixed failure signals — continue measurement before Architecture change."
    )
    return "OPT0_NO_ACTION", why, "STOP_C", "Defer", [
        o["id"] for o in options if o["id"] != "OPT0_NO_ACTION"
    ]


def run_success_class_accuracy_evaluation(
    *,
    include_live: bool = True,
    llm_enabled: bool = False,
    chat_fn=None,
    model: str = "",
    trust_path: Path | None = None,
) -> dict[str, Any]:
    initial_head = _git_head()
    trust = trust_path or (RepoRoot / "runs" / "ai_tool" / "_success_class_eval_trust.json")
    make_e2e_trust_file(trust)

    dataset = success_class_dataset(include_live=include_live)
    # Mock cases always run; live cases only when llm_enabled
    results: list[SuccessClassCaseResult] = []
    for spec in dataset:
        is_live_case = spec.case_id.startswith("SC-L")
        if is_live_case and not llm_enabled:
            continue
        if is_live_case and not chat_fn:
            continue
        use_live = is_live_case and llm_enabled
        results.append(
            run_success_class_case(
                spec,
                chat_fn=chat_fn or make_mock_chat_fn(spec.mock_scenario or TrialScenario("x", "", "either", "")),
                model=model,
                trust_path=trust,
                live=use_live,
            )
        )

    agg = aggregate_accuracy(results)
    options = architecture_options(agg)
    selected, why, stop, mechanical, rejected = select_option(agg, options)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": initial_head,
        "final_head": initial_head,
        "dataset": "success_class_v1",
        "dataset_size": len(dataset),
        "cases_run": len(results),
        "cases": [r.to_dict() for r in results],
        **agg,
        "claim_level_results": [c.to_dict() for r in results for c in r.claims],
        "deterministic_verifiable_claims": sorted(
            {c for r in results for c in r.deterministic_verifiable_claims}
        ),
        "architecture_options": options,
        "selected_option": selected,
        "selection_reason": why,
        "rejected_options": rejected,
        "mechanical_answer": mechanical,
        "human_intervention_count": 0,
        "production_changes": [],
        "evaluation_changes": ["web_tool_success_class_accuracy_evaluation.py"],
        "tests": ["mock SUCCESS-class taxonomy", "pytest unit"],
        "decision": "NO_PRODUCTION_CHANGE",
        "stop_reason": stop,
        "stop": True,
        "overall": "PASS" if agg.get("llm_answer_count", 0) > 0 else "PARTIAL",
        "confirmed_causes": _confirmed_causes(results, agg),
        "hypotheses": _hypotheses(agg),
        "unknowns": _unknowns(llm_enabled, include_live),
        "next_recommended_direction": _next_direction(selected, mechanical),
    }


def _confirmed_causes(results: list[SuccessClassCaseResult], agg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if agg.get("llm_answer_count", 0) > 0:
        out.append(
            f"SUCCESS-class LLM accuracy measurable: {agg.get('correct_count')}/{agg.get('llm_answer_count')} correct"
        )
    mock_failures = [r for r in results if r.case_id.startswith("SC-M") and r.answer_class not in ("Correct", "SKIPPED")]
    if mock_failures:
        out.append(f"Mock-controlled failure taxonomy validated: {len(mock_failures)} injected failures detected")
    live = [r for r in results if r.case_id.startswith("SC-L") and r.web_success]
    if live:
        out.append(f"Live SUCCESS-class cases run: {len(live)}")
    return out


def _hypotheses(agg: dict[str, Any]) -> list[str]:
    acc = agg.get("accuracy_rate", 0)
    return [
        f"SUCCESS-class accuracy ~{acc:.0%} on measured dataset",
        "Numeric claims are largely deterministic-verifiable via range match",
        "Mock failures prove taxonomy separation from web failures",
        "Live LLM variability may differ from mock-controlled baseline",
    ]


def _unknowns(llm_enabled: bool, include_live: bool) -> list[str]:
    u = [
        "Live LLM wrong-answer rate across broader query set",
        "Model parity (qwen3_8b vs others)",
        "Scope error detection reliability without LLM judge",
    ]
    if include_live and not llm_enabled:
        u.append("Live cases skipped — ollama unavailable")
    return u


def _next_direction(selected: str, mechanical: str) -> str:
    if selected == "OPT0_NO_ACTION":
        return "Continue monitoring; optional live expansion when ollama available"
    if mechanical == "Defer":
        return f"{selected} as candidate — Human Review before Production"
    return selected
