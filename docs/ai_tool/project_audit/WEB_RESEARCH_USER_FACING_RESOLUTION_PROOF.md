# Web Research User-Facing Resolution & Source Presentation Proof

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_160052_web_research_user_facing_resolution_proof/`  
**Model:** qwen3:8b (live arms) + deterministic proxy (offline)  
**Production changes:** NONE  
**Git commit:** NOT EXECUTED

---

## 目的

Web Evidence 取得後、**ユーザー向け会話として Source / 候補 / 差異 / 選択 / 出典確認まで成立するか**を PoC で実証する。

Production chain は維持:

```text
Search → Fetch → Extraction → Evidence → web_status → Boundary → LLM → User Conversation
```

本 Phase が検証するのはその先:

```text
Evidence → Candidate(s) → LLM Conversation → Source Presentation → User Follow-up
```

---

## A. 実現可能性

| 領域 | 結果 | 根拠 |
|------|------|------|
| Source attribution | **PASS** | Candidate に url / source_title / evidence_id 紐付け |
| Candidate representation | **PASS** | claim + evidence + source + verification observation |
| A/B presentation | **PASS** | PR-C03/C04/C05 で MULTI/UNRESOLVED；PR-C01 で SINGLE（一致時 A/B なし） |
| User selection | **PASS** | PR-C03/C05 follow-up で CA/CB 選択状態保持 |
| Follow-up conversation | **PASS** | 6/6 proof cases pass（live LLM 含む） |
| Source navigation | **PASS** | PR-C03/C06 「元ページを見せて」→ URL + 抜粋 |

### Q1–Q5

| Q | 結果 |
|---|------|
| Q1 Evidence metadata → user display | **PASS** |
| Q2 LLM multi-candidate judgment | **PASS**（mode 分岐；常時複数回答は禁止） |
| Q3 Candidate structure | **PASS** |
| Q4 Follow-up continuation | **PASS** |
| Q5 Source navigation without Production conflict | **PASS**（experimental presenter のみ） |

---

## B. 実装コスト

**MEDIUM**

| コンポーネント | Cost |
|----------------|------|
| `conversation_resolution/models.py` | LOW |
| `candidate_builder.py` | MEDIUM |
| `presenter.py` | LOW |
| `resolver.py` | MEDIUM |
| Production stdout/agent 統合 | HIGH（未実施） |

---

## C. Production 接続リスク

**MEDIUM**

- Agent / Prompt / Registry 未変更だが、会話状態・表示層追加は将来 HR 必須
- `agent.py` stdout 契約（raw result vs summary）との整合要検討

---

## D. LLM 会話品質

| 条件 | 評価 |
|------|------|
| Proxy offline | **不変** — 構造検証用 |
| Live qwen3:8b | **不変〜改善** — MULTI/UNRESOLVED で会話的説明可能；過度な URL 羅列なし |

失敗パターン（積極監視）:

- 不要な A/B 提示 → PR-C01/C02 で回避確認
- 必要なのに一方固定 → PR-C04 UNRESOLVED 確認
- Source 紐付け喪失 → なし（6/6 pass）

---

## E. 新規 Core（C0–C4）

| ID | Capability | Class | LLM 関係 |
|----|------------|-------|----------|
| CR-CANDIDATE-ENVELOPE | Candidate / Evidence Envelope | **C2** | 拡張 |
| CR-SOURCE-PRESENTATION | Source Presentation Layer | **C2** | 拡張 |
| CR-CONV-RESOLUTION | Conversation Resolution State | **C2** | 拡張 |
| CR-MECH-RESOLVER | Mechanical Conflict Resolver | **C0** | 置換 — **却下** |

**C3 新規:** なし（C2 investigation 先行）

---

## F. 公開実装との比較

| 参照 | 参考点 | 採用価値 |
|------|--------|----------|
| LangChain RAG citations | chunk metadata | LOW — 層が異なる |
| Perplexity-style (概念) | inline citation UX | MEDIUM — 表示参考のみ |
| OpenAI annotations | structured citations | LOW — credential/HR |
| 自作 enrich_web_tool_result | main_text + grounding | **HIGH** — experimental 拡張 |

「公開されているから採用」は **しない**。自作 Production chain + experimental envelope が基本。

---

## G. Production 変更

```text
Production Changes: NONE
```

---

## H. Decision

**INVESTIGATE**

| 判断 | 理由 |
|------|------|
| 6/6 proof cases PASS | 構造実現可能性確認 |
| 全 feasibility PASS | Q1–Q5 クリア |
| Production 接続 | 未提案 — Phase 2–4 待ち |
| HR | 不要 |

**Not selected:** PROMOTE_TO_PRODUCTION, STOP_NO_CHANGE, EXPERIMENTAL_CAPABILITY (C3)

---

## Proof Cases

| Case | Scenario | Mode | Result |
|------|----------|------|--------|
| PR-C01 | 一致 | SINGLE | PASS |
| PR-C02 | 数値近接 377,975 vs 378,000 | MERGED | PASS |
| PR-C03 | 定義差 2020 census vs 2024 estimate | MULTI | PASS |
| PR-C04 | 真競合 300万 vs 275万 (2024) | UNRESOLVED | PASS |
| PR-C05 | ユーザー B 選択 | MULTI + ADOPT_B | PASS |
| PR-C06 | 出典確認 | SINGLE + SHOW_SOURCE | PASS |

---

## 作らなかったもの

- Production Agent / Prompt / Registry 変更
- Mechanical Answer / Mechanical Resolver
- 常時 A/B UI
- Generic Retry/Fallback
- Research Transaction
- 新規 C3 Core

---

## Artifacts

| 種別 | Path |
|------|------|
| Experimental module | `ai_tool/experimental/conversation_resolution/` |
| Proof harness | `ai_tool/web_research_user_facing_resolution_proof.py` |
| Runner | `ai_tool/run_web_research_user_facing_resolution_proof.py` |
| Tests | `tests/ai_tool/project_audit/test_web_research_user_facing_resolution_proof.py` |
| Run | `runs/ai_tool/20260829_160052_web_research_user_facing_resolution_proof/` |

再実行:

```bash
python ai_tool/run_web_research_user_facing_resolution_proof.py
```

---

## 次 Phase 候補

1. **Live LLM UX evaluation** — 会話自然性の human review
2. **stdout / CLI 統合設計** — `agent.py` 契約を壊さない Source Presentation 経路（SCR 候補）
3. **C2 prototype hardening** — ConversationState persistence across agent turns

---

## Architecture Spec 整合（SCR-02）

- LLM 中心 — **維持**
- Mechanical Verification — observation のみ（Candidate verification フィールド）
- Web = 材料 — 真偽事前確定なし
- 複数回答 — 必要時のみ（MULTI/UNRESOLVED）
