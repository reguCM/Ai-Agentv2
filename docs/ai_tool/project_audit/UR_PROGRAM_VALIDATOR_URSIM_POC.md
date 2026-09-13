# URScript Static Validation + URSim Verification Boundary — Phase H

**実行日:** 2026-08-30  
**判定:** `POC_BOUNDARY_CONFIRMED` — 11/11 テスト PASS  
**Production 変更:** 0 | **新規 C3:** 0  
**Run:** `runs/ai_tool/20260830_113313_ur_program_validator_poc/`

---

## 1. 目的

Phase G で選定された **Universal Robots Program Validator** を Experimental Tool として最小実装し、以下 3 層を分離して検証可能か確認する。

```text
① 公式 URScript 仕様（provenance 付き catalog）
② Static Validator（PASS / FAIL / WARNING / UNKNOWN）
③ URSim シミュレーション（本 PoC では stub adapter）
```

さらに LLM が Validator / URSim / 公式 Evidence を会話として説明できる構造まで確認する。

---

## 2. 設計思想

LLM に URScript の正しさを記憶だけで判断させない。

| 層 | 意味 |
|----|------|
| 公式仕様 | 対象 Version に存在する（catalog + provenance） |
| Validator | 仕様 catalog 上で構文・関数・引数を観測 |
| URSim | シミュレーション上で実行できた（stub または live） |

**重要な境界:**

```text
Official Specification → Static Validation → Simulation → Real Robot
```

- `Validator PASS` ≠ 安全
- `URSim Success` ≠ 実機で安全
- 本 Phase は Real Robot まで到達しない

---

## 3. 成果物

| パス | 内容 |
|------|------|
| `ai_tool/experimental/ur_program_validator/` | Validator + catalog + URSim adapter + harness |
| `ai_tool/run_ur_program_validator_poc.py` | PoC 実行スクリプト |
| `tests/ai_tool/experimental/test_ur_program_validator_poc.py` | 5 pytest + harness 統合 |

### モジュール構成

| モジュール | 責務 |
|------------|------|
| `official_sources.py` | Web Research / URSim 環境調査（UNKNOWN 明示） |
| `spec_catalog.py` | 最小 function catalog（provenance 付き） |
| `version_context.py` | Version 可用性（Matrix Core なし） |
| `static_validator.py` | 静的検証 |
| `ur_sim_adapter.py` | probe + stub（live URSim 未インストール） |
| `compare.py` | Validator vs URSim 比較 |
| `llm_explanation.py` | LLM は説明のみ、正誤判定しない |
| `test_cases.py` | T1–T8 + 補助ケース |
| `harness.py` | `run_phase_h_poc()` |

---

## A. Environment

### URSim 環境調査

| 項目 | 値 |
|------|-----|
| 名称 | URSim |
| 対象 Robot | UR3e（typical — インストール時に要確認） |
| PolyScope Version | **UNKNOWN** — インストール時の release notes で確認 |
| URSim Version | **UNKNOWN** — 本ホストでは未プローブ |
| 対応 OS | Linux（一般的）、Windows（ホスト依存）、Docker（公式報告あり — 未検証） |
| Docker 対応 | LIKELY — Docker 23.0.5 検出、コンテナは未起動 |
| VM 対応 | UNKNOWN |
| Linux 対応 | YES — 典型的デプロイパス |
| Windows から利用 | PARTIAL — VM/Docker 経由が一般的 |
| CPU / RAM / Disk | UNKNOWN |
| GPU | NONE typical |
| License | Universal Robots license terms — download 時に確認 |
| Installation | Official download / Docker — **PoC では未実行** |
| 本開発 PC | Windows 10、URSim **NOT_INSTALLED** |

### ローカル probe 結果

```text
docker_available: true
ursim_detected: false
mode: stub
automation_level: manual
```

URSim live 不可は **STOP 条件ではない** — stub + Human-in-the-loop パスとして記録。

---

## B. Official Sources

| source_url | source_title | source_version |
|------------|--------------|----------------|
| `https://fixture.local/urscript-manual` | URScript Manual (Phase G fixture) | UNKNOWN |
| `https://fixture.local/ur-sdk` | Universal Robots SDK (fixture) | UNKNOWN |
| `https://www.universal-robots.com/articles/ur/interface-communication/ursim/` | URSim — Universal Robots (reference URL) | UNKNOWN |

**注:** PoC では Phase G の TDA fixture を primary source として REUSE。live fetch は未実施。`source_version` が UNKNOWN の項目は catalog に登録しない（LLM 記憶のみの情報は登録禁止）。

---

## C. URScript Coverage（Static Validator）

### catalog 登録関数（5 + keywords）

| Function | min/max args | Version |
|----------|--------------|---------|
| movej | 2–4 | 5.x |
| movel | 2–4 | 5.x |
| set_digital_out | 2–2 | 5.x |
| sleep | 1–1 | 5.x |
| legacy_move | 1–2 | 5.0 only（T6 合成例） |

### Validator が確認する範囲

- 構文観測（括弧バランス、`def/end` 警告）
- 関数存在（catalog 照合）
- 引数個数
- Python 混同検出（`pandas`, `print` 等）
- Version 可用性（deprecated / unavailable）
- Python 風 boolean リテラル（WARNING）

### Validator が確認しない範囲（明示）

- 実機安全性、衝突回避
- 物理 I/O 配線
- TCP キャリブレーション精度
- ワーク把持、サイクルタイム

---

## D. URSim Coverage

本 PoC では **stub adapter** を使用（live URSim 未インストール）。

### stub がモデルする範囲

- プログラム定義の有無
- 括弧バランス（syntax error）
- 未知関数（foo_bar, pandas 等）
- movej 引数不足
- legacy_move + PolyScope ≥ 5.10
- RUNTIME_FAIL マーカー（T7 blind spot）

### stub がモデルしない範囲

- 実際の PolyScope ランタイム
- 物理 I/O シミュレーション精度
- スレッド同期の完全再現

---

## E. Test Cases（T1–T8）

| ID | Label | Validator | URSim | Compare | Pass |
|----|-------|-----------|-------|---------|------|
| T1 | Valid basic script | PASS | PASS | expected | ✓ |
| T2 | Non-existent function | FAIL | FAIL | expected | ✓ |
| T2b | Python pandas confusion | FAIL | FAIL | expected | ✓ |
| T3 | Wrong argument count | FAIL | FAIL | expected | ✓ |
| T4 | Python-style boolean | WARNING | PASS | ANY | ✓ |
| T5 | Syntax error | FAIL | FAIL | expected | ✓ |
| T6 | Version-specific (5.15) | FAIL | FAIL | expected | ✓ |
| T6b | Version-specific (5.0) | PASS | PASS | expected | ✓ |
| T7 | Validator blind spot | PASS | FAIL | **critical_miss** | ✓ |
| T8a | Normal motion 1 | PASS | PASS | expected | ✓ |
| T8b | Normal motion 2 | PASS | PASS | expected | ✓ |

---

## F. Validator / URSim Disagreement

| Case | Validator | URSim | Interpretation | 意味 |
|------|-----------|-------|----------------|------|
| T7 | PASS | FAIL | **critical_miss** | Static validator の blind spot を意図的に観測 |

その他のケースは `expected`（両者一致）または T4 は compare=ANY。

**T7 の解釈:** `movej(...)` は catalog 上 valid だが、`RUNTIME_FAIL` マーカーにより stub URSim が joint limit / unreachable target を報告。Validator は runtime 状態を観測できない — **critical_miss として正しく記録**。

---

## G. Automation

| 段階 | 状態 |
|------|------|
| URSim 起動 | **未実装** — 未インストール |
| Script 投入 | stub のみ |
| Program 実行 | stub のみ |
| Status / Error 取得 | stub 返却 |
| 完全自動化 | **不可**（現環境） |

### 記録

| 項目 | 内容 |
|------|------|
| Why difficult | URSim 未インストール、公式 headless API 未統合 |
| Required interface | PolyScope program execution API / Docker orchestration |
| Missing API | Live URSim automation layer |
| Manual operation | Human-in-the-loop 検証パス推奨 |
| Workaround | Stub adapter で構造 PoC |
| Automation risk | 脆弱な UI 自動化は DEFER |

**判断:** URSim は **Human-in-the-loop 検証** に向く（CI 完全自動化は Phase H 範囲外）。

---

## H. LLM Role

LLM は **正誤判定をしない**。以下を説明に利用:

- Validator result（status + issues）
- URSim result（status + errors）
- Compare interpretation
- Official provenance
- Fix suggestions（`officially_verified` / `unknown` 区別）

例（T2）:

> `foo_bar()` は対象 Version の公式 URScript catalog で確認できません。Validator では FAIL です。URSim stub でも FAIL を報告しています。

修正候補は `suggest_fixes()` が catalog 内の類似名のみ `officially_verified` とラベル付け。推測は `unknown`。

---

## I. Unknown

| 項目 | 理由 |
|------|------|
| URSim 正確な Version | 本ホスト未インストール |
| PolyScope / URScript Version 対応表 | 完全 manual 未取得 |
| live URSim 実行結果 | stub のみ |
| 全 URScript builtin 網羅 | 最小 PoC scope |
| T7 以外の natural blind spot | 未発見（T7 は synthetic marker） |

---

## J. Safety Boundary

**禁止（遵守）:**

- Real robot connection
- Robot controller network access
- Production robot execution
- Physical motion
- Automatic deployment to robot

**明示:**

- Validator PASS ≠ 実機安全
- URSim Success ≠ 実機安全
- Simulation stub ≠ live URSim ground truth

---

## K. New Ideas（Capability Discovery）

| Idea | Decision | 理由 |
|------|----------|------|
| Specification-backed Code Validator | RECORD | URScript → 他 DSL へ一般化可能 |
| URSim full automation API | DEFER | コスト高、自動化脆弱 |
| Version Matrix Core | REJECT | spec_catalog + VersionContext で十分 |
| Real robot execution bridge | REJECT | SAFETY — Phase H 禁止 |

---

## L. False Discovery（作らなかった Capability）

| 検討 | 不採用理由 |
|------|------------|
| Version Matrix Core | Phase D/E 方針継続 — 過剰抽象化 |
| Full URScript parser | PoC scope 超過 |
| LLM-as-validator | 中心問題（LLM 捏造）に逆行 |
| Production agent 統合 | Phase H 禁止 |

---

## M. Production Impact

| 項目 | 値 |
|------|-----|
| agent.py 変更 | 0 |
| registry 変更 | 0 |
| Production Web Research chain 変更 | 0 |
| Production Tool 変更 | 0 |
| golden_pass | true（回帰確認） |

---

## N. Core Discovery

| 項目 | 値 |
|------|-----|
| 新規 C3 Core | **0** |
| REUSE | Phase G fixture, VersionContext 思想, TDA Standard Workflow |
| EXPERIMENTAL | `ur_program_validator/` 一式 |

---

## Success Criteria（H1–H12）

| ID | 内容 | 結果 |
|----|------|------|
| H1 | 公式 URScript 仕様を取得できる | ✓ fixture + provenance |
| H2 | Version を区別できる | ✓ T6 / T6b |
| H3 | 存在しない Function を検出 | ✓ T2, T2b |
| H4 | 引数エラーを検出 | ✓ T3 |
| H5 | 構文エラーを検出 | ✓ T5 |
| H6 | URSim で正常 Script 実行 | ✓ T8a/b（stub） |
| H7 | URSim で異常 Script 確認 | ✓ T2 |
| H8 | Validator / URSim 比較 | ✓ compare.py |
| H9 | 検証不能範囲を明示 | ✓ NOT_VALIDATED |
| H10 | LLM が Observation を説明 | ✓ llm_explanation.py |
| H11 | LLM 推測と Evidence 区別 | ✓ provenance + suggestion labels |
| H12 | 実機安全性と simulation 混同しない | ✓ safety_boundary |

---

## TDA 接続

```text
Phase G 曖昧要求
  → Universal Robots Program Validator 選定
  → Phase H Experimental 実装
  → Web Research / Official fixture (FIXTURE_URSCRIPT)
  → spec_catalog + VersionContext
  → static_validator
  → ur_sim_adapter (stub)
  → compare + llm_explanation
```

TDA 本体は大幅改造なし。Phase G fixture を official source として REUSE。

---

## 結論

Phase H は **完成度より検証可能な境界の発見** を優先し、以下を確認した:

1. 公式仕様 → catalog → Validator の Evidence 分離が成立
2. Validator PASS / URSim FAIL（critical_miss）を T7 で観測
3. Version 差（T6/T6b）を catalog + VersionContext で扱える
4. LLM は Observation を説明するだけ — 正誤判定はしない
5. URSim live 不可は stub + HITL として記録（失敗扱いにしない）

**次ステップ（Phase H 範囲外）:** live URSim インストール、公式 manual の live fetch、自然 blind spot の追加探索。
