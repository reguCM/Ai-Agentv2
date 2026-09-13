# Tool Change / Backward Compatibility Policy

**状態:** ADOPT CANDIDATE（ポリシー文書。実装・自動判定は NOT READY）

## 目的

既存 Tool を**変更してはいけない**のではなく、

> 既存利用者を壊さないことを基本とし、可能な限り後方互換な拡張として変更する。

ことを正式に整理する。

本ポリシーは **新規 Tool 作成**（[CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md)）と **既存 Tool 変更**の両方に適用する。Phase 1 の「Mapping による移行なし」は一時的な調査方針であり、本ポリシーと矛盾しない。

---

## 既存ポリシーとの関係（参照のみ・重複説明なし）

| 既存文書 | 本ポリシーとの関係 |
|----------|-------------------|
| [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) | 変更後の仕様を記述する |
| [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) | **外部から見える契約** — 互換性判断の基準 |
| [TEST_CONTRACT.md](./TEST_CONTRACT.md) | 契約が壊れていないことを検証する |
| [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) | **安全性は別軸** — Interface 互換だけでは不十分 |
| [CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md) | 変更を含む全体フロー |
| [CATALOG.md](./CATALOG.md) | `tool_status: deprecated` 等のライフサイクル |
| [VALIDATOR.md](./VALIDATOR.md) / [tests/](./tests/) | 構造検証・回帰（Phase 3-1） |
| `PROJECT_SPEC.md` §3.4 | Tool 作成は制御プロセス・人間承認 |

**調査結果:** `backward compatibility` / `breaking change` の専用文書は Phase 3-1 時点では**存在しなかった**。`version` フィールドは Specification / Catalog にあるが、運用ルールは未確定（後述 UNKNOWN）。

---

## 基本原則

### 原則 A — 既存 Tool は原則「拡張」で変更する

既存呼び出しがそのまま動く変更を第一候補とする。

```text
既存:  get_x()
変更後: get_x(optional_parameter=None)
```

Registry 上は同一 `name` / `module` / `function` のまま、**引数なし呼び出し**が引き続き有効であること（[TEST_CONTRACT.md](./TEST_CONTRACT.md) N-02 参照）。

### 原則 B — 既存引数を勝手に変更しない

以下は **Breaking Change 候補**（詳細は [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) の `must` / `must_not` と照合）:

| 変更 | 分類 |
|------|------|
| 必須引数の追加 | Breaking Change 候補 |
| 引数名変更 | Breaking Change |
| 引数型変更 | Breaking Change 候補 |
| 引数の意味変更 | Breaking Change |
| デフォルト値変更による既存挙動変更 | Compatibility Review Required |
| 戻り値の既存キー削除 | Breaking Change |
| 戻り値の既存キーの意味変更 | Breaking Change |

Registry `input` 形式と Agent の `function(**arguments)` 呼び出し（本番 `agent.py`）を前提とする。Ollama に公開される `parameters.required` への影響もレビュー対象。

### 原則 C — 出力も拡張を基本とする

既存利用者が `result["temperature"]` を参照している場合、新キー `fan_speed` の追加は原則 **Safe Extension**。

既存キーの削除・改名・意味変更は **Breaking Change 候補**。

契約の正本は Specification の `output_schema` と [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) の `must`（例: `get_gpu_status` の `observation_source: real` — [examples/existing_get_gpu_status.md](./examples/existing_get_gpu_status.md)）。

### 原則 D — 単純な拡張で対応できない場合

| 選択肢 | いつ検討するか |
|--------|----------------|
| **1. 新 Tool として作る** | 目的が大きく異なる、契約を共有できない |
| **2. 新 version / interface** | 同一ドメインだが契約を変えざるを得ない |
| **3. 既存 Tool を deprecated** | Catalog `tool_status: deprecated`（[CATALOG.md](./CATALOG.md)） |
| **4. 明示的 Migration** | 利用者・Registry・ドキュメントの移行手順が必要 |

PROJECT_SPEC の「人間承認を要する変更」と整合させる。自動 Migration・自動 Registry 更新は **禁止**（Phase 2/3-1 方針と同じ）。

---

## 変更分類

「変更禁止」ではなく、以下の 3 段階で判断する。

### Safe Extension（原則そのまま適用可）

既存利用者を壊さない可能性が**高い**。

- optional parameter 追加（既存呼び出しは不変）
- output key 追加（既存キーは不変）
- optional metadata 追加
- 新 Provider 対応（別 `tool_id`、既存 Local は不変）
- 内部実装改善（Contract・入出力契約不変）

**それでも:** 回帰テスト（既存 pytest / Tool 専用テスト）の実行を推奨。

### Compatibility Review Required（人間レビュー必須）

影響範囲の確認が必要。

- デフォルト値変更
- エラー処理・`error_format` の変更
- output schema の複雑な拡張（既存キーの型狭義化など）
- performance / timeout の大幅変更
- `risk_level` / `permissions` / `visibility` の変更
- `description` の意味的変更（LLM の Tool 選択に影響）

### Breaking Change（既存利用者の追随が必要）

- required parameter 追加・削除・改名
- parameter 意味変更
- output key 削除・改名・意味変更
- `tool_id` / Registry `name` 変更
- `side_effect` クラス変更（Safety 別軸 — 下記）
- [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) の `must` / `must_not` 削除・弱体化

Breaking Change は **原則 原則 D**（新 Tool / version / deprecated / Migration）を検討する。

---

## Safety は別軸（Interface compatibility ≠ Safety compatibility）

通常の後方互換ルール**だけ**では判断しない。

| 変更例 | Interface 上 | Safety 上 |
|--------|--------------|-----------|
| read_only → write | 引数同じでも | **Safety Review 必須** |
| network_access false → true | 出力同じでも | **Safety Review 必須** |
| risk low → high | 互換に見えても | **Compatibility Review + Safety** |

詳細な実行パイプライン・write/modify 禁止は [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) を参照。本ポリシーでは重複説明しない。

---

## 変更ワークフロー

新規作成フロー（[CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md)）に、変更時は以下を**追加**する。

```text
変更前 Contract / Specification（保存・Git）
    ↓
変更意図・Compatibility 分類（Safe / Review / Breaking）
    ↓
変更後 Tool Specification
    ↓
Mechanical Validation（[VALIDATOR.md](./VALIDATOR.md) / pytest）
    ↓
Compatibility 判定（本ポリシー + 人間）
    ↓
Implementation
    ↓
既存 Test Contract + 追加テスト
    ↓
「新機能が動く」＋「既存の使い方が壊れていない」
    ↓
Safety Check（[SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md)）
    ↓
Human Approval
    ↓
Registry / Catalog 更新（手動）
```

**重要:** 「新機能が動く」だけでは不十分。**既存の代表入力・既存 output key・既存 contract.must** が維持されることを [TEST_CONTRACT.md](./TEST_CONTRACT.md) で確認する。

---

## Regression Test（Phase 3-1 との接続 — ポリシーのみ）

現時点では**自動 Compatibility 判定は未実装**（NOT READY）。

将来の接続候補:

```text
既存 Tool 変更
    ↓
既存 pytest（tests/test_*.py 本番 + tool_creation/tests/）
    ↓
変更前後 Specification diff（手動または将来 CLI）
    ↓
既存利用パターンのスナップショットテスト（HUMAN_REQUIRED 期待値）
    ↓
Compatibility 確認
```

Phase 3-1 の `docs/ai_tool/tool_creation/tests/` は **Validator / gold spec** の回帰であり、個別 Tool の利用パターン回帰とは別レイヤ（[PHASE3_1_REPORT.md](./PHASE3_1_REPORT.md)）。

---

## Versioning（FUTURE CONSIDERATION / UNKNOWN）

以下は**未確定**。本ポリシーでは方式を確定しない。

| 項目 | 状態 |
|------|------|
| Tool ID versioning（`local:get_gpu_status@v2`） | UNKNOWN |
| Specification `version` フィールドの bump 規則 | UNKNOWN |
| Semantic versioning 運用 | FUTURE CONSIDERATION |
| schema version（`tool_spec.schema.json`） | EXPERIMENTAL（Creation Layer のみ） |
| Migration version / 自動移行 | NOT READY（明示 Migration のみ想定） |

`version` を上げることと Breaking Change の対応関係は、将来 Catalog + Registry 運用と一緒に決める。

---

## 変更例

### Example 1 — optional parameter 追加

```python
# 既存: search_web(query)
# 変更後: search_web(query, limit=None)  # limit 省略時は従来どおり
```

→ **Safe Extension** 候補。既存 `search_web(query)` は有効。N-02・既存テストで確認。

### Example 2 — required parameter 追加

```python
# 既存: foo()
# 変更後: foo(region)  # region 必須
```

→ **Breaking Change** 候補。Agent / LLM の既存 tool_call は失敗しうる。原則 D を検討。

### Example 3 — output key 追加

```json
{"temperature": 41, "fan_speed": 1200}
```

→ **Safe Extension** 候補。`temperature` は不変。`output_schema` に key 追加を Specification に反映。

### Example 4 — output key 削除

`temperature` を削除し `temp_c` のみ返す。

→ **Breaking Change**。原則 D または Migration 文書化。

### Example 5 — 内部実装変更、Contract 不変

nvidia-smi パース実装のリファクタ。入出力 dict 形状・`must_not` 遵守は不変。

→ **原則安全（Safe Extension）**。ただし [TEST_CONTRACT.md](./TEST_CONTRACT.md) Safety・Failure カテゴリと既存 `tests/test_gpu_real_observation.py` で回帰確認。

### Example 6 — read-only Tool を write 可能に

filesystem Tool に書き込みモードを追加。

→ Interface が拡張に見えても **Safety Review 必須**（[SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md)）。`side_effect`・`risk_level`・`agent_tool_gate` を再評価。自動実行は禁止のまま。

---

## Registry 更新時の注意

`registry/tools.json` 更新は**人間承認後・手動**（[CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md)）。

| Registry フィールド変更 | 通常の互換性 |
|-------------------------|--------------|
| `input` に required 追加 | Breaking Change 候補 |
| `description` のみ | Compatibility Review（LLM 影響） |
| `risk` 引き上げ | Safety + Review |
| `visibility` 変更 | Review（公開範囲変更） |
| `module` / `function` 変更 | Breaking Change 候補 |

Catalog の `experiment_status` / `adoption_status` は [CATALOG.md](./CATALOG.md) の三層モデルに従い、Breaking Change 後は `adoption_status` の再レビューを想定。

---

## 文書マップ

```text
TOOL_SPECIFICATION     → 何を作るか / 変更後の仕様
TOOL_CONTRACT          → 外部から見える契約（互換性の基準）
TEST_CONTRACT          → 契約をどう検証するか
TOOL_CHANGE_POLICY     → 既存 Tool をどう変更するか（本文書）
SAFETY_BOUNDARY        → 安全性をどう判断するか（別軸）
CREATION_WORKFLOW      → 新規・変更を含む進め方
CATALOG                → 稼働・実験・採用状態
VALIDATOR / tests/     → 構造の機械検証・回帰
```

---

## 状態ラベル

| 項目 | ラベル |
|------|--------|
| 本ポリシー文書 | ADOPT CANDIDATE |
| 自動 Compatibility 判定 | NOT READY |
| Versioning 運用 | UNKNOWN |
| Tool 変更専用 pytest | FUTURE CONSIDERATION |

---

## 今回やらないこと

- Compatibility Validator の実装
- Registry 自動更新
- 本番 Tool の変更
- `agent.py` / `tools/` の改修

実装接続は [NEXT_STEPS.md](./NEXT_STEPS.md) / Phase 3-2 以降で検討。
