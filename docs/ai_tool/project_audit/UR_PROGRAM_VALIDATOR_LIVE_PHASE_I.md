# Live URSim Verification + Tool Development Loop — Phase I

**実行日:** 2026-08-30  
**判定:** `BLOCKED`（Live URSim 不可）+ Development Loop `LOOP_COMPLETED`（stub 経由）  
**Production 変更:** 0 | **新規 C3:** 0  
**Run:** `runs/ai_tool/20260830_114329_ur_program_validator_phase_i/`

---

## 1. 目的

Phase H で確認した 3 層境界を **Live URSim** で再検証し、さらに TDA による Tool Development Loop が成立するか確認する。

| 検証軸 | 内容 |
|--------|------|
| **I-A** | Static Validator ↔ Live URSim 比較 |
| **I-B** | Requirement → TDA → URScript → Validator → URSim → LLM 説明 |

---

## 2. 最終判断

```text
Decision: BLOCKED
Live mode: False
Dev loop: LOOP_COMPLETED (stub fallback)
Test expectations: 6/6 PASS (stub mode)
```

**BLOCKED 理由（実測）:**

```text
Docker CLI: インストール済 (23.0.5)
Docker daemon: 停止 (com.docker.service Stopped)
WSL: 未インストール
→ Docker Desktop バックエンド起動不可
→ Live URSim コンテナ起動不可
```

失敗を成功扱いしていない。Live 検証はインフラ整備後に `run_ur_program_validator_phase_i.py` で再実行可能。

---

## Environment

### ホスト（実測）

| 項目 | 値 |
|------|-----|
| OS | Windows 10 |
| CPU | 12th Gen Intel Core i5-12400 |
| RAM | ~64 GB |
| Docker CLI | 23.0.5 |
| Docker daemon | **停止** |
| WSL | **未インストール** |
| GPU | 未プローブ（URSim 通常不要） |

### Phase I 選定ターゲット（公式 Web Research）

| 項目 | 値 |
|------|-----|
| Image | `universalrobots/ursim_e-series:5.15` |
| PolyScope | e-Series 5.15 |
| Robot model | UR5（`ROBOT_MODEL=UR5` env） |
| Web UI | localhost:6080 |
| VNC | localhost:5900 |
| Dashboard | localhost:29999 |
| Primary / Secondary | 30001 / 30002 |
| Programs mount | `/ursim/programs` |

PolyScope X イメージ（`ursim_polyscopex`）は存在するが、Phase H/H catalog との連続性のため e-Series を選択。

---

## Official Sources（Phase I 再調査）

| URL | タイトル |
|-----|----------|
| https://hub.docker.com/r/universalrobots/ursim_e-series | Official URSim e-Series Docker |
| https://docs.universal-robots.com/.../ursim_docker.html | Setup URSim with Docker (UR ROS2 docs) |
| https://www.universal-robots.com/developer/communication-protocol/dashboard-server/ | Dashboard Server :29999 |
| https://hub.docker.com/r/universalrobots/ursim_polyscopex | PolyScope X（参考 — 未選択） |

Phase H の fixture 情報は **再引用せず**、上記公式 URL を Phase I provenance として記録。

---

## Installation

| 段階 | 結果 |
|------|------|
| `docker pull universalrobots/ursim_e-series:5.15` | **未実行** — daemon 停止 |
| Container start | **未実行** |
| Smoke test | **スキップ** |
| PolyScope UI | **未確認** |

### 代替案（BLOCKED 時）

1. WSL2 インストール → Docker Desktop 起動
2. `docker pull universalrobots/ursim_e-series:5.15`
3. `python ai_tool/run_ur_program_validator_phase_i.py` 再実行

---

## Live Test（stub fallback 結果）

Live 不可のため stub adapter で I-T1〜I-T6 を実行。

| ID | Validator | URSim (stub) | Compare | Pass |
|----|-----------|--------------|---------|------|
| I-T1 | PASS | PASS | expected | ✓ |
| I-T2 | FAIL | FAIL | expected | ✓ |
| I-T3 | FAIL | FAIL | expected | ✓ |
| I-T4 | FAIL | FAIL | expected | ✓ |
| I-T5 | FAIL | FAIL | expected | ✓ |
| I-T6 | PASS | PASS | — | ✓ (T7: NOT_FOUND) |

---

## T7 Result（Live 再検証）

| 項目 | Phase H (stub) | Phase I (live/stub) |
|------|----------------|---------------------|
| 手法 | `RUNTIME_FAIL` 合成マーカー | マーカーなしで探索 |
| Validator | PASS | PASS |
| Simulation | FAIL | PASS (stub) |
| 解釈 | critical_miss | **NOT_FOUND** |

**記録:** Stub では synthetic marker で critical_miss を観測したが、Live（または marker なし stub）では自然 blind spot を **再現できなかった**。  
「再現しなかった ＝ Validator 完全」とはしない — runtime 语义は Static では観測不可のまま。

---

## Validator Results / URSim Results / Comparison

Phase H の `static_validator.py` + `compare.py` を REUSE。  
Live adapter は `live_ursim_manager.py`:

- Level 2 自動化設計: Dashboard `:29999` + Secondary Client `:30002`
- Docker 起動 + programs volume + smoke test 実装済
- daemon 可用時に live path へ切替

---

## Automation Level

| Level | 状態 |
|-------|------|
| 0 完全手動 | **現在** — daemon 停止 |
| 1 半自動 | コード準備済（script 配置 + 手動 Run） |
| 2 自動実行 | **実装済** — `execute_urscript_live()` |
| 3 Regression | DEFER — 次 Phase 候補 |

### 確認済み公式インターフェース（文献）

- Docker API / volume mount
- Dashboard Server TCP :29999
- Secondary Client :30002（URScript 送信）
- Programs `/ursim/programs`

### 未確認

- .urp ファイル load/play 完全 headless パス
- Remote Control モード要件の live 実測

---

## Tool Development Loop

**Requirement:**

> URScriptで簡単なロボットプログラムを作りたい。必要な仕様を調べて、実際にシミュレータで確認できるところまでやってほしい。

### フロー（実測）

```text
Requirement Gate → RESEARCH_REQUIRED
Goal Abstraction L0–L3
Web Research (TDA-G URScript fixture)
Decision Support + Spec Draft
Catalog-backed URScript 生成
Static Validator
URSim (stub — live blocked)
Compare + LLM explanation
```

**Decision:** `LOOP_COMPLETED`  
**Attempts:** 2（catalog-backed revision、最大 3 回制限内）

### LLM 記録の分離

Attempt 2 で Validator PASS + URSim PASS でも、  
「LLM が正しいコードを理解した」とは **記録していない**。  
記録は Observation のみ。

---

## LLM Role

| 担当 | 非担当 |
|------|--------|
| Requirement 解釈、Research 解釈 | URScript 正誤の記憶判定 |
| Observation 説明 | 失敗原因の捏造確定 |
| Fix suggestion ラベル（verified/unknown） | Mechanical ground truth |

---

## Unknown

- Live URSim 実行結果（daemon 停止）
- PolyScope 5.15 の全 builtin 網羅
- I-T6 自然 blind spot
- Remote Control / brake release の live 挙動
- 実機安全性

---

## Safety Boundary

**禁止（遵守）:** Real Robot / Controller / Physical Motion / Production Deployment

**明示:**

- URSim Success ≠ 実機安全
- Validator PASS ≠ runtime 正しさ
- Live 自動化は secondary client 経由 — 完全 PolyScope UI パスではない

---

## Capability Discovery

| Idea | Decision |
|------|----------|
| Simulation-backed Development Assistant | RECORD |
| Research Transaction Core | REJECT |
| URSim PolyScope X image | DEFER |
| WSL2 bootstrap automation | RECORD |
| Version Matrix Core | REJECT (Phase H 継続) |

### 上位概念化観測

```text
URScript Validator
  → Specialized Language Validator
  → Specification-backed Code Validator
  → Simulation-backed Development Assistant
```

抽象化のための新 Core は作らず、既存モジュール REUSE。

---

## REUSE / RECORD / DEFER / REJECT

| 項目 | 判定 |
|------|------|
| Phase H validator + compare | REUSE |
| TDA standard_workflow | REUSE |
| research_reuse.py | REUSE |
| live_ursim_manager.py | EXPERIMENTAL |
| Version Matrix Core | REJECT |
| Real robot bridge | REJECT |

---

## Production Impact

| 項目 | 値 |
|------|-----|
| agent.py | 0 |
| registry | 0 |
| Production Web Research | 0 |
| golden_pass | true |

---

## Core Discovery

**新規 C3: 0**

---

## Success Criteria（I1–I11）

| ID | 結果 | 備考 |
|----|------|------|
| I1 Live start | ✗ | BLOCKED |
| I2 Robot select | ✗ | BLOCKED |
| I3 Official script | ✓ | catalog-backed |
| I4 Normal confirm | ✓ | I-T1 validator PASS |
| I5 Abnormal confirm | ✓ | I-T2/3/4 FAIL |
| I6 Compare | ✓ | compare.py |
| I7 T7 attempted | ✓ | NOT_FOUND |
| I8 Automation level | ✓ | Level 0 判定 |
| I9 LLM observation | ✓ | |
| I10 Provenance | ✓ | Phase I sources |
| I11 Dev loop | ✓ | LOOP_COMPLETED |

---

## 成果物

```
ai_tool/experimental/ur_program_validator/
  live_environment.py      # Phase I Web Research + host probe
  live_ursim_manager.py    # Docker + smoke + live execution
  live_test_cases.py       # I-T1〜I-T6
  development_loop.py      # TDA minimal loop
  phase_i_harness.py       # Phase I orchestration

ai_tool/run_ur_program_validator_phase_i.py
tests/ai_tool/experimental/test_ur_program_validator_phase_i.py
```

---

## 次ステップ（Phase I 範囲外）

1. WSL2 + Docker Desktop 起動
2. `run_phase_i_poc(attempt_live=True)` 再実行
3. Smoke test + I-T1 live 実行
4. T7 自然 blind spot の追加探索
5. Level 3 regression suite（DEFER）

---

## 結論

Phase I は **Live URSim が現環境で BLOCKED** であることを実測で確認した。  
ただし以下は Phase H から進展している:

1. 公式 URSim Docker 環境の **再調査**（Phase H 情報を盲信しない）
2. Live adapter + Level 2 自動化 **実装**（daemon 可用時に実行可能）
3. TDA Development Loop **LOOP_COMPLETED**（stub 経由、Evidence 分離維持）
4. T7: synthetic blind spot は stub のみ — live では **NOT_FOUND**（Validator 完全と解釈しない）

```text
LLM → Web Research → Official Docs → Spec → Validator → Simulator → Observation → LLM Conversation
```

構造自体は BLOCKED 状態でも **Development Loop まで実証**。Live 層は環境整備後に差し替え可能。
