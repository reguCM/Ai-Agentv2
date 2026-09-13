# Web Research User-Facing Resolution E2E Integration Investigation

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_160958_web_research_user_facing_resolution_e2e/`  
**Model:** qwen3:8b (live resolution layer) + deterministic proxy (offline CI)  
**Production changes:** NONE  
**Git commit:** NOT EXECUTED

---

## 目的

直前 Phase の fixture PoC（PR-C01〜C06）を、**Production mirror 相当の agent 経路**（`run_canonical_web_eval`）に接続し、

```text
Production Web Tool → Canonical Web Eval → Evidence
  → Experimental Candidate Builder → Conversation Resolution → LLM → User
```

が実 Web 相当条件下でも成立するかを実証する。

---

## Architecture

```text
run_canonical_web_eval()          # gate + enrich + boundary 同経路
        ↓
AgentWebLoopResult.tool_executions
        ↓
evidence_sources_from_loop()      # 複数 read_url_text を EvidenceSource 化
        ↓
initialize_conversation()         # 既存 PoC
        ↓
resolve_initial_turn / handle_follow_up
        ↓
UserFacingPresentation
```

**新規 Experimental コンポーネント**

| ファイル | 責務 |
|----------|------|
| `ai_tool/experimental/conversation_resolution/e2e_adapter.py` | loop→Evidence 抽出、failure 分類、canonical 収集 |
| `ai_tool/web_research_user_facing_resolution_e2e.py` | E2E ケース定義・評価 harness |
| `ai_tool/run_web_research_user_facing_resolution_e2e.py` | Runner |

---

## 実証

| 項目 | 結果 |
|------|------|
| 単一Candidate | **PASS** |
| 定義差 | **PASS** |
| 真の競合 | **PASS** |
| 複数Candidate | **PASS** |
| User Selection | **PASS** |
| Conversation State | **PASS** |
| Source Presentation | **PASS** |
| URL integrity | **PASS** |
| Web/LLM failure separation | **PASS** |

**Pass count:** 10/10（canonical 8 + live 2）

### ケース一覧

| ID | 種別 | シナリオ | 経路 |
|----|------|----------|------|
| E2E-C01 | A | 一致2ソース → SINGLE | canonical + fixture |
| E2E-C02 | B | 2020 census vs 2024 estimate → MULTI | canonical + fixture |
| E2E-C03 | C | 300万 vs 275万 → UNRESOLVED | canonical + fixture |
| E2E-C04 | D | ADOPT_B + state 保持 | canonical + fixture |
| E2E-C05 | E | SHOW_SOURCE → URL + 抜粋 | canonical + fixture |
| E2E-C06 | F | 弱いソース → MULTI（確定化しない） | canonical + fixture |
| E2E-C07 | — | 数値近接 → MERGED | canonical + fixture |
| E2E-C08 | — | 非 Wikipedia 日本語 | canonical + fixture |
| E2E-L01 | Live | ja.wikipedia 大阪市 | canonical + live fetch |
| E2E-L02 | Live | en.wikipedia Osaka | canonical + live fetch |

---

## Architecture — Core Discovery

| Capability | Class | 判断 |
|------------|-------|------|
| CR-CANDIDATE-ENVELOPE | **C3** | canonical E2E adapter で loop→Candidate 接続を実証。本 Phase の唯一 C3 昇格 |
| CR-SOURCE-PRESENTATION | **C2** | 出典提示は安定。Production stdout 統合は未 |
| CR-CONV-RESOLUTION | **C2** | 選択状態保持は canonical 経由でも安定 |

Mechanical Resolver: **C0 rejected**（変更なし）

---

## Production

| 項目 | 結果 |
|------|------|
| Production 変更数 | **0** |
| Registry 変更 | **0** |
| Agent 変更 | **0** |
| Prompt 変更 | **0** |
| Golden GT1–GT6 | **6/6 PASS**（live fetch 実行時）/ fixture-only CI では skipped 除き PASS |
| pytest | **PASS**（web_status + web_evidence_pipeline + E2E tests） |

---

## Failure Taxonomy（分離確認）

| Layer | 用途 |
|-------|------|
| WEB_FAILURE | loop error / fetch 全失敗 |
| EVIDENCE_FAILURE | main_text 不足 |
| CANDIDATE_FAILURE | Candidate 未生成 |
| LLM_FAILURE | （本 Phase では deterministic 主体のため未観測） |
| USER_RESOLUTION_FAILURE | 選択未保持 |

canonical ケースでは **NONE**。Search 失敗と Resolution 失敗は adapter 層で分離可能。

---

## 外部比較

| ツール / 概念 | 分類 | 理由 |
|---------------|------|------|
| LangChain document loaders + metadata | **参考** | chunk attribution の metadata パターンのみ |
| Perplexity 型 source-grounded 回答 | **参考** | citation UX。競合時の会話解決は不透明 |
| OpenAI annotations / file_search | **不採用** | hosted + credential 依存 |
| 本 repo `enrich_web_tool_result` | **採用** | Production Evidence 基盤として維持 |
| 本 repo Experimental Conversation Resolution | **採用** | LLM 中心・ユーザー選択・出典提示に適合 |

---

## 最終 Decision

**`EXPERIMENTAL_RETAIN`**

- Production 接続は **行わない**（Human Review 必須）
- Experimental adapter + PoC は **保持**
- 次 Phase: live multi-source search、stdout 統合設計、数値抽出 heuristics 改善

---

## 最終質問（Cursor 自己評価）

1. **Web Research を「使える会話機能」に近づけたか？**  
   **部分的に Yes。** canonical 経路接続により、Search→Fetch→Evidence の先に Candidate/会話/出典まで一連で動く。ただし Production Agent 本体には未接続。

2. **User-facing な価値が生まれているか？**  
   **Yes（Experimental 層）。** 定義差・競合を A/B 羅列ではなく会話＋選択＋出典提示として扱える。情報圧縮だけではない。

3. **LLM 能力を置き換えず拡張できているか？**  
   **Yes。** Mechanical Answer なし。LLM は説明・整理・follow-up に専念。

4. **A/B 的異情報を保持できるか？**  
   **Yes。** E2E-C02/C03/C06 で MULTI/UNRESOLVED を確認。

5. **ユーザー選択を後続会話で利用できるか？**  
   **Yes。** E2E-C04 で CB 選択が turn 2 以降も保持。

6. **出典ページまで辿れるか？**  
   **Yes。** E2E-C05 + live L01/L02 で Candidate 紐付け URL を提示。捏造 URL なし。

7. **Production へ入れる価値があるか？**  
   **将来あり。** ただし stdout 契約・会話状態・multi-fetch 安定性の HR が先。

8. **入れる場合の最小部分は？**  
   **`evidence_sources_from_loop` + Candidate Envelope のみ。** Presenter/Resolver は feature flag 付き Experimental から段階導入。

9. **入れない理由は？**  
   **まだ未成熟。** Agent 統合・live search 多ソース・数値 heuristic（年号誤抽出）が残る。不要ではない。

10. **Web Research 機能は実用到達点にあるか？**  
    **「調査可能」には到達、「日常会話に耐える」には未到達。**  
    単一ソース Wikipedia は動くが、search 主導の multi-source live、競合時の LLM 自然さ、Production UX 統合が未完了。技術 PASS 10/10 でも、ユーザー体験としては **Experimental デモ段階**。

---

## 実行方法

```bash
python ai_tool/run_web_research_user_facing_resolution_e2e.py
```

Offline CI:

```bash
pytest tests/ai_tool/project_audit/test_web_research_user_facing_resolution_e2e.py -q
```

---

## Related

- [WEB_RESEARCH_USER_FACING_RESOLUTION_PROOF.md](./WEB_RESEARCH_USER_FACING_RESOLUTION_PROOF.md) — 直前 fixture PoC
- [WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md](./WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md) — SCR-02 設計思想
