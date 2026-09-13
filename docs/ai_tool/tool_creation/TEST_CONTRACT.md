# Test Contract

新規 Tool が満たすべき共通テスト契約。**状態:** ADOPT CANDIDATE

各カテゴリで不要な項目は `NOT_APPLICABLE` と明記する。

## 記録形式

```yaml
tool_id: local:example
test_contract:
  normal: [...]
  boundary: [...]
  invalid: [...]
  failure: [...]
  safety: [...]
```

## 1. Normal（正常系）

| ID | 内容 | 必須 |
|----|------|------|
| N-01 | 代表的入力で成功 | yes |
| N-02 | 最小構成入力で成功 | 入力がある場合 |
| N-03 | 戻り値が `output_schema` に適合 | yes |

**既存参照:** `tests/test_gpu_real_observation.py` — GPU 実測・フォールバック禁止

## 2. Boundary（境界）

| ID | 内容 | 記録 |
|----|------|------|
| B-01 | 最小値 | 数値パラメータがある場合 |
| B-02 | 最大値 | 同上 |
| B-03 | 空文字列 | 文字列パラメータがある場合 |
| B-04 | 空コレクション | 配列パラメータがある場合 |
| B-05 | null / 省略 | optional パラメータ |
| B-06 | 長大入力 | 文字列・配列 |

**引数なし Tool（`get_gpu_status`）:** B-01〜B-06 は `NOT_APPLICABLE`

## 既存 Tool 変更時

新規カテゴリの追加に加え、**変更前の代表入力・既存 output key が維持される**ことを確認する。互換性分類は [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) を参照。

「新機能が動く」テストだけでは不十分。既存 N-01 / N-03 相当が引き続き pass することを回帰の最低ラインとする。

## 3. Invalid（不正入力）

| ID | 内容 | 必須 |
|----|------|------|
| I-01 | 型違い | 入力がある場合 |
| I-02 | 不正 enum 値 | enum がある場合 |
| I-03 | 必須項目欠落 | 必須パラメータがある場合 |
| I-04 | 未知キー | `additionalProperties: false` の場合 |

期待: 例外または `error_format` 準拠の error dict。**固定値フォールバック禁止**（GPU Tool 契約）。

## 4. Failure（障害）

| ID | 内容 | 記録 |
|----|------|------|
| F-01 | 対象不存在 | ファイル・リソース参照 Tool |
| F-02 | 外部サービス失敗 | network / subprocess |
| F-03 | timeout | timeout 定義がある場合 |
| F-04 | permission denied | filesystem / gate |

**既存参照:** `get_gpu_status` — nvidia-smi 失敗時 `ok: false`, `observation_source: real` 維持

## 5. Safety（安全）

| ID | 内容 | 必須 |
|----|------|------|
| S-01 | 禁止操作を実行しない | yes |
| S-02 | 想定外 write なし | read_only Tool |
| S-03 | 想定外 modify なし | read_only Tool |
| S-04 | 想定外 network なし | `network_access: false` |
| S-05 | AST / 静的 Safety | Builder 経由の場合 |

**既存参照:** `test_tool()` 内 `assess_registry_tool_code()` — 生成コード AST ゲート

## 既存 `test_tool()` との差

| 項目 | `test_tool()` | Test Contract |
|------|---------------|---------------|
| 引数 | なしのみ | カテゴリ別に定義 |
| 出力検証 | なし（return_value 記録のみ） | output_schema 照合 |
| Safety | AST のみ | 操作契約 + AST |
| 統合 | Registry 直実行 | execute_tool / Provider（将来） |

## Phase 1 で不足（UNKNOWN / 次フェーズ）

- 共通 pytest フィクスチャ（未実装）
- Test Contract の CI 強制（未実装）
- MCP / API Tool 用の Contract テンプレート（文書のみ）
- パラメータ化テストの Registry 駆動生成

## 採用ラベル

| 項目 | ラベル |
|------|--------|
| 契約定義そのもの | ADOPT CANDIDATE |
| 自動実行基盤 | NOT READY |
| MCP 向け拡張 | UNKNOWN |
