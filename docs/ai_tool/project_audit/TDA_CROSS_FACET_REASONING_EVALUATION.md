# TDA Cross-Facet Reasoning Evaluation (Phase K)

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_163429_cross_facet_reasoning`  
**判定:** 既存 TDA は **Facet を保存・併記できる**。中心ケースは併記だけで安全側 NO にできる。ただし **既存消費者は K-7 要求を Ownership Release 判断まで組み立てない**。  
**Production 変更:** 0  
**新規 C3:** 0

これは LLM 対話の採点ではない。既存モジュール（ResearchRecord / Reuse / Goal Abstraction / Decision Factor / Idea Preservation / Standard Workflow）が、Phase J の Facet を **構造としてどこまで使えるか** の offline 実測である。

実行:

```bash
python ai_tool/run_tda_cross_facet_reasoning_evaluation.py
pytest tests/ai_tool/project_audit/test_cross_facet_reasoning.py -q
```

---

## K-1 Existing Capability Audit

| 機能 | 存在 | ロボット Facet を扱えるか |
|------|------|---------------------------|
| ResearchRecord | はい | `environment_facts` / `conflicts` / `unknowns` / `api_observations`。**`facet_records[]` は型に無い** |
| facet_records[] | Phase J JSON のみ | 公式 dataclass ロードで **落ちる**（実測 extra keys: `facet_records`, `capability_observations`, `phase_results`, `c3_decision`, `production_changes`） |
| Evidence | `sources` + `api_observations` | 関係は **散文**。グラフ API は無い |
| VersionFact | はい | python/cuda/os 向け。`does_not_apply` は **dict としては残る**が `VersionFact` dataclass では落ちる |
| ResearchState | はい | unknowns/conflicts のセッション保持。Facet 結合 API 無し |
| Research Reuse | はい | 技術名は polars/urscript/python/cuda。**control_authority キーは無い** |
| Goal Abstraction | はい | PolyScope パターン → API Observation / Research Reuse / Mechanical Validator REJECT。**Ownership Release は出ない** |
| Decision Factor | はい | version/license/python。操作権ではない |
| Conflict / Unknown | はい | リスト。検索すれば関係文を読める。第一級の遷移ではない |
| Idea Preservation | はい | トークン一致。英語 K-7 で Guard が再評価ヒット |
| Standard Workflow | はい | Gate → Goals → Reuse → Candidate Decision。ロボット状態遷移は見ない |

**結論（K-1）:** 新規 Core 無しで **保存は可能**。不足は「結合して判断する消費者」であり、Matrix Core ではない。

---

## K-2 Facet Memory

Fixture（切断後スナップショット）:

```text
transport=disconnected
control_authority=Dashboard
operational_mode=AUTOMATIC
operational_mode_source=Dashboard
```

| ID | 質問 | 期待 | Facet 併記 | 備考 |
|----|------|------|------------|------|
| K2-A | TCP は切断されているか | YES | **YES** | 単一 Facet 取得 1/1 |
| K2-B | TCP 切断だけで mode 所有は解除されたか | NO | **NO** | AUTOMATIC/Dashboard が残っている |
| K2-C / 人間操作権を断定 | NO/UNKNOWN | **NO** | Transport だけでは証明しない |

対照として **unsafe transport proxy**（切断=人間操作、製品ポリシーではない）は K2-B を **YES** と誤る。False inference **4 件**。

中心ケースは、**値が残っている限り併記を読めば防げる**。防ぐのは「TCP だけを見る」読み方である。

---

## K-3 Cross-Facet

| ID | 期待 | Facet のみ | conflicts 付き typed |
|----|------|------------|----------------------|
| K3-1 切断→人間操作可 | NO | NO | NO + J-1 散文 |
| K3-2 切断後 mode=NONE? | NO | NO（AUTOMATIC 残） | NO |
| K3-3 clear で人間操作完了? | CONDITIONAL | **UNKNOWN**（clear 結果が無い） | **CONDITIONAL** |
| K3-4 error 無し=実行 | NO | NO（STOPPED） | NO（accept≠execute conflict） |
| K3-5 他社実装=UR | NO | **UNKNOWN** | **NO** |

**Cross-Facet Accuracy:** Facet 併記 **5/7**。Relationship 散文 **7/7**。

A で落ちる 2 件は意図どおり: **clear の意味** と **ベンダー同一視禁止** は値の併記だけでは足りず、関係/conflict が要る。

---

## K-4 Unknown Preservation

`cycle_controller=UNKNOWN` + 他社未実測を unknowns に保持。

「Cycle Controller は存在しますか？」→ **UNKNOWN**（Facet / typed とも 1/1）。FANUC/KUKA から UR の存在を推定しない。

---

## K-5 Version Boundary

5.15.2 と 5.17 Security 制限を混在。

「5.17 制限が 5.15.2 にもあるか」→ Facet 併記は **UNKNOWN**（YES にしない）。typed の `does_not_apply` dict では **NO**。

`VersionFact` dataclass は `does_not_apply` を持たない → 公式 VersionFact 経路だけだと境界が落ちる。

---

## K-6 Matrix vs Relationship

同じ質問: TCP 切断で人間操作へ戻ったか。

| 表現 | 判定 | 説明 |
|------|------|------|
| A Facet のみ | **NO** | Dashboard 所有が残っている（安全側） |
| A typed（conflict 無し） | **NO** | 同上。J-1 文は引用しない |
| B Facet 値 | **NO** | 値は A と同じ |
| B typed + conflicts | **NO** | **J-1「TCP disconnect does not clear operational mode」を引用** |

Verdict はどちらも NO。**説明が変わる**（`verdict_changed_A_to_B_typed=true`）。理想どおり: A で安全側、B で実測根拠。

---

## K-7 Decision Support（既存消費者）

要求: Dashboard 通信を切れば人間が PolyScope を安全に再開できる Tool を作れ。

| | 日本語要求 | 英語要求 |
|--|------------|----------|
| Gate | RESEARCH_REQUIRED（PolyScope） | RESEARCH_REQUIRED |
| Research Reuse | **no_reuse** | **partial_reuse**（topic token が英語 Record に当たる） |
| Goal 派生 | API Observation / Research Reuse / Mechanical Validator REJECT | 同左 |
| `clear operational mode` が reuse 材料に出るか | いいえ | **いいえ** |
| Idea 再評価 | ヒットなし | **Controller Ownership Guard**（trigger 部分一致） |

既存 Standard Workflow は **send → disconnect → human control** を実装案としては出さない（Spec Draft も候補が空に近い）。同時に **明示的 Release（clear）+ PolyScope 確認** にも到達しない。

Reuse の LLM 向け要約は python/cuda/license 固定であり、control_authority を読まない。

日本語要求は過去 Record と **マッチしない**。保存されていても再利用されない。

---

## K-8 Idea Discovery

テスト中に自然に出た名前（実装していない）:

| 名前 | 出たか | 判定 |
|------|--------|------|
| API Existence Observation | はい（UR パターン） | **REUSE** |
| Research Reuse | はい | **REUSE** |
| Mechanical API Validator | はい（既存 REJECT） | **REJECT** |
| Controller Ownership Guard | 英語 Idea 再評価のみ | **DEFER** |
| Ownership Release / Human Handoff / State Snapshot / Cycle | 消費者からは出ず | **DEFER** |
| Cross-Facet Reasoning Core | 出さず（本評価で検討） | **DEFER** |

---

## K-9 False Reasoning

| 主張 | 期待 | Facet 併記 | typed + 関係 |
|------|------|------------|----------------|
| TCP が無いなら Remote ではない | UNKNOWN/NO | UNKNOWN | UNKNOWN |
| Remote でないなら Human が所有 | NO | NO | NO |
| Dashboard 成功 = 実行 | NO | NO | NO |
| Simulation なら状態確認不要 | NO | NO | NO |
| Validator PASS = URSim PASS | NO | NO | NO |
| FANUC にある = UR にある | NO | UNKNOWN | NO |
| 5.17 は 5.15 に適用 | NO/UNKNOWN | UNKNOWN | NO |
| Program Stop = Ownership 解放 | NO/UNKNOWN | NO | NO |

False Inference 件数: unsafe proxy **4** / facet 併記 **0** / typed 関係 **0**。  
False-reasoning 正答: Facet **7/8**（K9-6 は UNKNOWN で NO 未達）、typed 関係 **8/8**。

---

## K-10 Metrics（実測のみ）

| Metric | 実測 |
|--------|------|
| Facet Accuracy | **1/1 = 1.0** |
| Cross-Facet Accuracy | 併記 **5/7 ≈ 0.714** / 関係散文 **7/7 = 1.0** |
| Unknown Preservation | **1/1** |
| Version Isolation | 併記 UNKNOWN で YES 回避 **1/1** / typed NO **1/1** |
| False Inference | proxy 4 / 併記 0 / 関係 0 |
| Evidence Awareness（typed 関係） | **18/19 ≈ 0.947** |
| Capability Discovery | 既存 UR パターン 3 + Guard 再評価 1。Release/Handoff は未発見 |
| Existing Reuse | 日本語 K-7 **no_reuse** / 英語 **partial_reuse**。clear は未使用 |

---

## 到達度

```text
記憶できる          YES   environment_facts / conflicts / unknowns
    ↓
検索できる          PARTIAL  公式フィールドは可。facet_records は落ちる
    ↓
再利用できる        PARTIAL  英語 topic は partial。日本語は no_reuse
    ↓
複数 Facet 同時参照  POSSIBLE キー併記はある。消費者は参照しない
    ↓
Facet 間関係        PARTIAL  第一級グラフ無し。conflicts 散文で足りる場合あり
    ↓
Unknown を保持      YES    unknowns[] / UNKNOWN 値
    ↓
Version 境界        PARTIAL  dict では可。VersionFact 型では does_not_apply 脱落
    ↓
Decision に反映     NO     K-7 は clear / handoff に未到達
    ↓
新しい上位概念      PARTIAL  Guard は seed 再評価のみ。Release は出ない
```

**総合:** Research は「検索結果＋メタデータ」として保存されている。中心ケースを **構造として誤 YES にする必然は無い**。一方、既存 Decision Support はそれを **判断材料として組み合わせていない**。

---

## K-11 Core Creation Gate

| 対象 | 判定 |
|------|------|
| ResearchRecord + conflicts + unknowns | **REUSE** |
| facet_records[] を型へ載せる | **RECORD**（今は extra JSON。必須 Core ではない） |
| RequirementFacets に robot キー | **DEFER** |
| reuse_conversation_material が authority を出す | **DEFER** |
| Cross-Facet Reasoning Core | **DEFER** |
| Relationship Graph Core | **REJECT** |
| Matrix Memory Core | **REJECT** |

中心ケースは「切断後も AUTOMATIC/Dashboard」という **残存 Facet の併記**で NO にできる。グラフ Core は過剰。不足は K-7 消費者と日本語 Reuse マッチであり、専用 Reasoning C3 を今作る根拠にはならない。

---

## 最重要判定

現在のローカル TDA は、Industrial Robot Control Model を **検索可能な記録としては保持できる**が、**「TCP 切断 = 人間に操作権が戻った」を既存 Workflow が自ら否定して clear operational mode まで導く判断器にはなっていない**。

防ぐ力は Record の **併記と conflict 散文** にある。使う力はまだ **OSS/環境 Decision Support** の形のままである。
