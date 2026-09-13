# TDA Relevant Facet Routing Integration (Phase M)

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_172718_relevant_facet_routing`  
**Production 変更:** 0  
**新規 C3:** 0  
**判定:** `EXPERIMENTAL_RETAIN`（default `facet_routing="off"` のまま）

今回の問いは「Relevant Facet Selection を作れるか」ではない。

**Requirement に応じて Research の必要部分だけを Decision Support へ届けることで、現在の Standard Workflow より実際に良くなるか。**

```bash
python ai_tool/run_tda_relevant_facet_routing_evaluation.py
pytest tests/ai_tool/project_audit/test_relevant_facet_routing.py -q
```

---

## 最重要判定（実測）

| Mode | 何を Decision Support へ渡すか | Relevant Recall | Irrelevant Suppression | K-7 最小 Facet + Conflict |
|------|-------------------------------|-----------------|------------------------|---------------------------|
| **A** Legacy Existing（`facet_routing=off`） | Candidate 比較のみ。Reuse summary は python/cuda/license | **0.00** | 1.00（何もロボット Facet を出さない） | 0/5、Conflict 未到達 |
| **B** Full Research | 保存済み `facet_records[]` 全件 | **0.86** | **0.25** | 5/5、Conflict 到達。OSS ノイズ同梱 |
| **C** Relevant Routing（本命） | Alias + 格納 `pull_with` の Relevant Slice | **0.83** | **0.92** | **5/5、Conflict 到達** |

**回答:** Mode C は Mode A より明確に良い（K-7 の Transport / Control Authority / Operational Mode / Mode Source / Handoff と「TCP切断では Human Handoff を保証できない」Evidence が届く）。Mode B より Recall はわずかに低く、Suppression は大幅に高い。ただし planted OSS トークン（M6-7）と Gate 誤判定（M6-5）、alias 欠落（M6-2 `program_state`）が残るため、**Standard Workflow のデフォルトにはしない。Experimental adapter として保持。**

Reasoning / Matrix / Graph Core は作っていないし、作る実測根拠もない。

---

## M-1 Existing Workflow Audit（実装前に相当する結論）

Phase F Standard Workflow:

```text
Requirement
→ Gate
→ L0/L1/L2
→ Capability Discovery
→ Research Reuse Check
→ 不足分のみ Web
→ Candidate
→ Decision Support
→ Tool Spec
```

| # | 確認項目 | 実測 |
|---|---------|------|
| 1 | RequirementFacets の生成地点 | Gate 通過後の research path。`extract_requirement_facets`。フィールドは technologies / python / cuda / os / license / topic_tokens。**ロボット Facet は出ない** |
| 2 | Research Reuse が検索する情報 | `_facet_overlap`: license / python / cuda / version / source / topic / OSS 名。`control_authority` キーは無い。日本語 UR 要求は多くの場合 `no_reuse` |
| 3 | Decision Support へ渡る ResearchRecord | **渡らない。** `compare_candidates_for_decision(candidates)` のみ |
| 4 | `facet_records[]` を Workflow が使えるか | Phase M 前は **否**（Record に載っても読まない）。Phase M 後は `facet_routing != off` のときだけ Router が読む |
| 5 | ResearchRecord 全件渡し | 既存経路には **無い**。Mode B（`full`）で初めて可能 |
| 6 | Reuse summary だけを渡す箇所 | `llm_material = reuse_conversation_material(...)` が python/cuda/license 固定。Routing on 時のみ Slice を追記 |

**Relevant Facet Selection を挿入できる既存地点:** Research Reuse / Web の直後、API Observation と Decision Support の前。Gate `RESEARCH_NOT_REQUIRED` では実行しない（JSON Tool を複雑化しない）。

Default は `facet_routing="off"`。Phase F テストは変更なし（6/6 PASS）。

---

## M-2 Minimal Routing Contract

```text
Requirement
    ↓
Relevant Facet Set
    ↓
ResearchRecord
    ↓
Relevant Research Slice
    ↓
Evidence / Unknown / Conflict
```

これは Reasoning Engine ではない。Facet の正誤判定もしない。

「今回の Requirement に関係する既存 Research 情報はどれか」を選び、**value / evidence / unknown / conflict / version / provenance** を後段へ渡す Routing。

実装: `ai_tool/experimental/development_assistance/relevant_facet_router.py`  
配線: `run_standard_workflow(..., facet_routing="off"|"full"|"relevant")`

---

## M-3 / M-4 Mapping と実装範囲

Phase L の catalog / alias / `pull_with` を再利用した。

- `operational_mode_source.pull_with = [operational_mode]` — 文面に AUTOMATIC が無くても、Dashboard 所有の companion として Mode 値を届ける（推論ではない。格納メタデータ）。
- `docker.pull_with = [wsl2, storage, network_ports]` — Docker 環境要求で Port / WSL を同梱。

禁止したもの（未実装）: Reasoning Core / Matrix / Graph / Knowledge Graph / Vector DB / RAG / 新しい Memory DB。

---

## M-5 Three Workflow Modes

同一 Requirement・同一 `ResearchStore`（Phase L catalog を seed）で比較。LLM 真偽判定はしていない。Web は `tda=None` のため全 Mode 0 検索（Reuse 経路の差ではなく **Routing 経路の差** を測る）。

---

## M-6 Core Test Cases（実測）

| Case | Mode A | Mode B | Mode C |
|------|--------|--------|--------|
| **M6-1** Robot Human Handoff | recall 0。Conflict 未到達 | recall 1。OSS 漏洩 | **recall 1。** transport / authority / mode / mode_source / handoff。Conflict 到達 |
| **M6-2** URScript Execution | 0 | 1 | **0.80** — `program_state` 欠落（文面は「実行できるか」、alias は「実行可能」） |
| **M6-3** Docker Environment | 0 | 1（OSS 漏洩） | **1.00** — docker + companion（wsl2 / storage / ports） |
| **M6-4** Version Conflict | 0。5.17 を隔離できない（材料が無い） | 1。Conflict 到達 | **1.00。** version + permission。`do not mix 5.17 into 5.15.2` 保持 |
| **M6-5** Cycle Unknown | Gate 早期終了 | 同じ（Routing 未実行） | 同じ。**失敗地点は Router ではなく Requirement Gate** |
| **M6-6** Docker Port 再利用 | 0。Reuse Check も `no_reuse` | 全件 | **1.00** — docker / ports。authority / handoff は出さない |
| **M6-7** Irrelevant Suppression | 0（ロボット Facet も出さない） | 全件 + OSS | **ロボット Facet は揃う。** 要求文に埋め込んだ Python/CUDA/License/CPU は alias 一致で漏洩 |
| **M6-8** JSON Tool | `EARLY_EXIT_GATE`、検索 0、Routing 段なし | 同じ | **同じ。複雑化なし** |

---

## M-7 Evidence / Conflict / Unknown Preservation

Mode C で Slice に載った Facet について:

| Envelope | 実測 |
|----------|------|
| Evidence | **1.00** |
| Unknown | **1.00** |
| Conflict | **1.00** |
| Version / Provenance | 選択 Facet に付与（K-7 は `phase_l_fixture` + ursim 5.15.2） |

文字列 ID フィルタではない。例: Operational Mode は `value=AUTOMATIC`、`pulled_with=operational_mode_source`。Transport は Conflict `TCP disconnect does not clear operational mode` を保持。

---

## M-8 K-7 Regression

要求:

> URSimをAgentから操作したあと、Dashboardとの通信を切断すれば、人間がPolyScopeから安全に操作を再開できるToolを作ってください。

| | Mode A | Mode B | Mode C |
|--|--------|--------|--------|
| 到達 Facet | （なし） | カタログ全件 | transport, control_authority, operational_mode, operational_mode_source, human_handoff |
| 「TCP切断だけでは Human Handoff を保証できない」 | **未到達** | 到達（ノイズ付き） | **到達** |
| False Inference（切断＝操作権返還） | 材料不足（発明はしない） | Conflict があるため抑制 | Conflict があるため抑制 |

Mode C は本命として **期待最小セット + Evidence を満たした。**

---

## M-9 Decision Quality（M6 8ケース平均、実測）

| Metric | Mode A | Mode B | Mode C |
|--------|--------|--------|--------|
| Relevant Recall | 0.00 | 0.86 | **0.83** |
| Irrelevant Suppression | 1.00 | 0.25 | **0.92** |
| Evidence Preservation | n/a（Slice なし） | （全件のため保持） | **1.00** |
| Unknown Preservation | n/a | — | **1.00**（到達した Slice 内） |
| Conflict Preservation | n/a | — | **1.00**（到達した Slice 内） |
| Version Isolation | 材料なし | 5.17 mix 禁止テキストあり | **維持**（M6-4） |
| Decision Accuracy（ケース定義の到達） | 0.13 | 0.88 | **0.85** |
| False Inference | 発明なし / 判断材料なし | Conflict 保持 | Conflict 保持 |
| Research Reuse（既存 Check） | 日本語 UR は `no_reuse` | 同じ | **同じ Check。ただし Store の facet_records は Routing が読む** |
| Web Search Reduction | 0（本ハーネスは tda なし） | 0 | 0（増加なし） |

Mode A の Suppression 1.00 は「何も出さない」ことによる見かけ上の良さであり、Relevant Recall 0 とセットで読む。

---

## M-10 Complexity / Regression

| 指標 | Mode A | Mode B | Mode C |
|------|--------|--------|--------|
| 平均 Stage 数 | 6.75 | 7.50 | 7.50 |
| 平均処理時間 (ms) | 0.47 | 1.17 | 0.59 |
| 平均 Web 検索 | 0 | 0 | 0 |
| JSON（M6-8）Stage | 6、Routing なし | 6、Routing なし | **6、Routing なし** |

研究経路では Routing 段が **+1**。Gate 終了では **+0**。Tool Spec Draft は Candidate が無いと従来どおり生成されない（本ハーネスは tda なし）。Phase F `test_run_phase_f_offline` は **PASS / ADOPT / c3_implemented=0**。

「Facet Selection を入れたせいで JSON Tool が複雑化する」は **起きていない。**

---

## M-11 Failure Analysis（Mode C）

```text
Requirement理解
      ↓
Goal Abstraction
      ↓
Facet Selection
      ↓
Research Reuse
      ↓
Evidence Routing
      ↓
Decision Support
      ↓
Tool Spec
```

| Case | 失敗地点 | 内容 |
|------|----------|------|
| M6-2 | **Requirement → Facet Mapping不足** | `program_state` の alias は「実行可能」。要求は「実行できるか」 |
| M6-5 | **Requirement理解（Gate）** | Cycle/Unknown 要求なのに `RESEARCH_NOT_REQUIRED`。Router は呼ばれない。JSON 保護のための Gate skip が、誤った早期終了にも適用される |
| M6-7 | **Facet Selection** | 要求文に埋め込んだ Python/CUDA/License/CPU は alias overlap では除外できない（Relevance 判定ではないため） |
| M6-1 / M6-3 / M6-4 / M6-6 / M6-8 / K-7 | （成功） | Evidence Routing まで到達 |

Router が悪いと一括しない。Gate と Mapping が先に折れている。

---

## M-12 Idea Preservation

| アイデア | 判定 |
|----------|------|
| Cross-Facet Reasoning Core（Phase K DEFER） | **DEFER**（今回も作らない） |
| Relationship Graph / Knowledge Graph | **REJECT** |
| Matrix Core / RAG / Vector DB / 新 Memory DB | **REJECT** |
| `ResearchRecord.facet_records` | **REUSE**（dataclass へ optional 追加。Core ではない） |
| `relevant_facet_router` | **EXPERIMENTAL** |
| DecisionFactor を Slice の封筒にする | **REUSE** |

---

## M-13 Adoption Gate

**EXPERIMENTAL_RETAIN**

- Mode C は Mode A より K-7 と判断材料で有効。
- JSON Gate への副作用は実測ゼロ。
- Facet Mapping 不足と planted-token 漏洩があるため、Standard Workflow のデフォルトにはしない。
- default は `off` のまま。呼び出す実験経路でのみ `facet_routing="relevant"`。

ADOPT しない理由は「効果がない」ではなく、**alias overlap を Relevance 判定とみなして本番既定にするには不足がある**ため。

---

## M-14 最終回答

> Requirement に応じて Research の必要部分だけを Decision Support へ届けることで、現在の Standard Workflow より実際に良くなるか？

**部分的に Yes（実測）。Standard 既定にするほどではない。**

1. **Mode A** は Research を保存できても、Decision Support にロボット Facet を届けない。K-7 は Conflict 未到達。
2. **Mode B** は Recall 最大だが Python/CUDA/License を Handoff 要求へ混ぜる。
3. **Mode C** は K-7 に必要な Slice と Evidence を届け、Mode B よりノイズが少ない。JSON Tool は複雑化しない。

既存構造（RequirementFacets / Reuse summary）だけでは足りず、**最小 Experimental adapter** で接続できた。新規 C3 は不要。
