# TDA Relevant Facet Selection Evaluation (Phase L)

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_171307_relevant_facet_selection`  
**Production 変更:** 0  
**新規 C3:** 0

今回答える問いは「Research を保存できるか」ではない。

**Requirement に応じて、保存済み Research のどの部分を判断材料として取り出せるか。**

LLM による真偽判定はしていない。Mode A/B/C は **判断材料パッケージ** の比較である。

```bash
python ai_tool/run_tda_relevant_facet_selection_evaluation.py
pytest tests/ai_tool/project_audit/test_relevant_facet_selection.py -q
```

---

## L-1 既存構造監査（実装前に相当する結論）

| 構造 | Requirement → robot Facet を選べるか |
|------|--------------------------------------|
| `RequirementFacets` | **否。** フィールドは technologies / python / cuda / os / license / topic_tokens のみ |
| `extract_requirement_facets` | polars/urscript 等の OSS 名。control_authority は出ない |
| `assess_reuse` / `_facet_overlap` | 当たれば license/python/cuda/version/source/unknowns。ロボット Facet キーは無い |
| `reuse_conversation_material` | python/cuda/license 固定。TCP vs ownership は欠落 |
| `Goal Abstraction` | PolyScope ヒット時は API Observation / Research Reuse。Ownership は出ない |
| `DecisionFactor` | candidate の version/license/python。Facet スライスの受け皿には **型として使える** |
| `facet_records[]` | Phase J JSON にはある。**ResearchRecord dataclass には無い**（ロードで落ちる） |
| Standard Workflow | 上記を直列するだけ。Relevant Facet Selection 段は **無い** |

Harness だけで検証できる範囲: 既存 Mode A の出力採点、fixture 上の `facet_records` を alias でスライス（Mode C）、Unknown/Conflict を `DecisionFactor` に載せる。  
新規 Core 無しではできないこと: Production Workflow が PolyScope 再開要求から Control Authority を選ぶこと。

---

## L-2 Requirement → Relevant Facet

要求: Agent 操作後、人間が PolyScope から安全に再開したい。

| Facet | なぜ Relevant か（fixture 理由） | Mode C |
|-------|----------------------------------|--------|
| Control Authority | 誰がペンダントを操作できるか | **選択**（人間が） |
| Human Handoff | PolyScope から再開 | **選択** |
| Safety State | 安全に | **選択** |
| Operational Mode | Automatic ロック | **欠落**（要求に Manual/Automatic 語が無い） |
| Operational Mode Source | Dashboard 所有 | **欠落**（L2 文面に Dashboard 無し） |
| Transport | 切断がよく同時に語られる | **欠落**（L2 は切断と言っていない） |
| Controller / Program State | 再開条件 | **欠落** |

正解リストを決め打ち必須にはしていない。L2 の Mode C recall は **0.38**。要求に無い Facet は alias では取れない。これは Reasoning 不足ではなく **要求に書かれた語と格納 alias の overlap** の限界。

---

## L-3 Irrelevant Suppression

要求: 人間が PolyScope から操作を再開できるか。

Mode C 選択: `control_authority`, `human_handoff` のみ。  
Python / CUDA / License / GPU / CPU / Documentation Version は **選ばれない**（suppression **1.0**）。

---

## L-4 要求を変えると集合が変わる

| Case | Mode C 選択（抜粋） | 期待との差 |
|------|---------------------|------------|
| L4-A TCP切断→操作権 | transport, authority, mode_source, handoff | operational_mode 欠落 |
| L4-B URScript 実行 | urscript_api, version, ursim, program_state, execution_observation | Control Authority **非選択**（not_primary 漏れなし） |
| L4-C PCで起動 | ursim, version | Docker/WSL/RAM は文面に無く欠落 |
| L4-D 5.17 Permission を 5.15.2 へ | version, permission_feature | conflict/evidence はメタ Facet として文面一致せず |

**Requirement ごとに集合は変わる。** 「全部のロボット Facet を毎回出す」実装にはなっていない。

---

## L-5 Evidence Routing

Mode C の各 Facet について、格納した evidence / unknown / conflict を `DecisionFactor` に載せた。勝者は出していない。

既存 `compute_decision_factors(candidate)` は相変わらず python/license だけ。**接続できたのは「スライス → DecisionFactor 型」であり、既存 candidate Decision Support 本体ではない。**

---

## L-6 Unknown Routing

要求: 外部トリガで N 回 Cycle を安全に実行できるか。

`cycle_controller` と `safety_state` が選択され、どちらも **status=unknown** のまま DecisionFactor に到達。他社 Cycle で埋めない。**1.0**

---

## L-7 Conflict Routing

要求: 5.15.2 で B の Permission を使えるか。

`permission_feature` が **conflict**（5.17 を 5.15.2 へ混ぜない）として到達。match 扱いで適用可能とはしない。Version isolation **1.0**

---

## L-8 Reuse Routing

要求: 以前の URSim 5.15.2 について Docker 環境だけ詳しく。

| | |
|--|--|
| Mode C 選択 | docker, ursim, version |
| 過去 Record から再利用 | 3（docker / ursim / version） |
| 文面に無く Fresh 候補 | cpu_virtualization, ram |
| 期待にあったが文面に無い | wsl2, network_ports |

既存 `assess_reuse` は license/python/version の missing を出すだけで、**Docker だけ再調査**にはならない。

---

## L-9 K-7 Regression

要求: 切断すれば人間が PolyScope から安全に再開できる Tool を作れ。

Mode C が選んだ最低限:

- transport（切断）
- control_authority（人間が）
- operational_mode_source（Dashboard）
- human_handoff（PolyScope / 再開）

**operational_mode は欠落（4/5 = 0.8）。** 文面に Automatic が無い。

Conflict `TCP disconnect does not clear operational mode` は **DecisionFactor に到達**（`k9_conflict_reached=true`）。

既存 Standard Workflow の reuse 材料には handoff / clear operational mode は出ない（Phase K と同じ）。

---

## L-10 Metrics（実測）

| Metric | Mode A 既存抽出 | Mode B 全件ダンプ | Mode C alias スライス |
|--------|-----------------|-------------------|------------------------|
| Relevant Recall | **0.02** | **1.00** | **0.67** |
| Irrelevant Suppression | **1.00**（何も選ばないため） | **0.00** | **1.00** |
| Evidence Routing | 既存は OSS 因子のみ | 全部 | **1.00**（スライス分） |
| Unknown Routing (L6) | — | 埋もれる | **1.00** |
| Conflict Routing (L7) | — | 埋もれる | **1.00** |
| Version Isolation | — | 5.17 も同居 | **1.00** |
| Reuse Routing (L8) | version 程度 | 全 Facet | Docker 関連 **3** |
| Decision Improvement | 基準 | ノイズ増 | recall **+0.65 vs A** |

追加 Facet は誤りにしていない（L6 の controller_state 等）。

---

## L-11 Mode A / B / C

LLM 採点はしていない（真偽判定器にしない）。材料の質だけ比較した。

| | 内容 | 実測 |
|--|------|------|
| A Requirement → 既存 workflow | python/cuda/urscript 抽出 | ロボット Facet をほぼ取れない。抑制は高いが空に近い |
| B Requirement → Record 全体 | 全 catalog | recall 1。Python/CUDA/License が常に混入 |
| C Requirement → alias スライス → Evidence/Unknown/Conflict → DecisionFactor | 格納 alias の出現 | recall 0.67、抑制 1.0、K-7 conflict が届く |

**全部渡すより、要求に関連するスライスを渡す方が、抑制と Conflict の可視性で有利。**  
ただし C は既存 Standard Workflow ではなく、Harness 内の **alias overlap** である。これは Core ではなく retrieve-a-slice の実験。

---

## 到達度

```text
Requirement
    ↓ 既存 Goal Abstraction     … ドメインは UR と分かるが Facet は出ない
    ↓ Relevant Facet Selection  … 既存 RequirementFacets では未到達
                                  Harness alias スライスでは部分到達
    ↓ Research Reuse            … OSS/version のみ。Docker-only 再調査は未
    ↓ Evidence / Conflict / Unknown
                                … Record にはある。C で DecisionFactor に載る
    ↓ Decision Factor           … 型は REUSE。中身は candidate だと python/license
    ↓ Decision Support          … 既存提示は candidate 比較。スライス提示は実験のみ
```

---

## L-12 No New Core Gate

| 対象 | 判定 |
|------|------|
| `facet_records` を Record に保存 | **REUSE**（JSON extra。型への追加は RECORD） |
| `DecisionFactor` を Unknown/Conflict の入れ物にする | **REUSE** |
| 既存 `RequirementFacets` をロボット選択器にする | **REJECT**（フィールドが違う） |
| alias によるスライス Helper | **EXPERIMENTAL**（Harness で効果を実測。未 Production） |
| Standard Workflow へ接続 | **DEFER** |
| Reasoning / Matrix / Graph Core | **REJECT** |

operational_mode のように **文面に無いが J-1 では対になる Facet** は、alias だけでは取れない。それを Graph Core にする必要はまだ無い。`operational_mode_source` 選択時に Record 上の対を一緒に取る、程度の orchestration は **DEFER**。

---

## 最終回答

現在の Agent/TDA は Research を **保存**できる。既存 Decision Support は Requirement から **OSS/環境 Facet** しか取り出せない。

Industrial Robot Control Model については、`facet_records` に付けた alias で **必要な部分だけ取り出すことは可能**であり、そのスライスなら Unknown と「切断 ≠ 操作権返還」Conflict を判断材料として DecisionFactor まで届けられる。

それは新しい Reasoning Core ではない。**要求に応じた Record の切り出し**である。Workflow への組み込みはこの Phase では行わない。
