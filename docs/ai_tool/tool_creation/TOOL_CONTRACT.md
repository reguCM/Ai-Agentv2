# Tool Contract

Tool が**何をするか**と**何をしてはいけないか**を分離した機械的契約。

**目的:** LLM プロンプト用テキストではなく、Validator・レビュー・テストの一次参照。  
**状態:** ADOPT CANDIDATE

## 形式

Specification 内の `contract` ブロック、または独立ファイル `contracts/<tool_id>.yaml`:

```yaml
tool_id: local:get_gpu_status
contract:
  can:
    - read_gpu_metrics_via_nvidia_smi
    - return_unknown_on_observation_failure
  cannot:
    - fabricate_gpu_values
    - write_to_filesystem
    - modify_system_state
  must:
    - set_observation_source_real
    - include_ok_and_status_fields
  must_not:
    - fallback_to_hardcoded_temperature
    - invoke_network_apis
```

## フィールド定義

| キー | 意味 | 検証方法 |
|------|------|----------|
| `can` | 許可される能力・操作 | 実装レビュー、代表テスト |
| `cannot` | 明示禁止 | Safety テスト、静的解析 |
| `must` | 常に満たす不変条件 | 出力スキーマ・ユニットテスト |
| `must_not` | 絶対禁止行為 | Safety テスト、コードレビュー |

## LLM への投入について（Phase 12 方針）

- **常時 Full Context 投入はしない**（NH13/NH13-7 の知見）
- Contract 全文は Catalog / Specification に保持
- LLM には必要時のみ `description` + 縮約 `can`/`cannot` を Selector 経由で渡す（将来）

## 既存 Tool との対応

| 既存の暗黙契約 | Tool Contract 化 |
|----------------|------------------|
| GPU「固定値フォールバック禁止」 | `must_not: fallback_to_hardcoded_*` |
| `observation_source: real` | `must: set_observation_source_real` |
| Registry `risk: low` | Security セクション + `cannot: modify_*` |
| `agent_tool_gate` 人間確認 | 実行層。Contract とは分離 |

## Selector / Validator との関係

```text
Selector（LLM）: 「get_gpu_status を使いたい」
       ↓
Validator: contract.must / cannot + safety + gate
       ↓
許可時のみ Execution
```

**SELECT ≠ VALIDATE** — LLM の選択を Validator が必ずしも許可しない。

## 契約の安定性（変更時）

既存 Tool 変更時は `must` / `must_not` / `output_schema` の後方互換を [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) で判定する。契約の定義方法は本文書のまま。

## 記述ガイド

1. `can` は 3〜7 個に抑える（観測可能な動詞）
2. `must_not` は過去の障害・DF 知見から逆引き
3. 曖昧語（「適切に」）は使わない
4. MCP Tool は Server 宣言を信用せず、クライアント側 `cannot` で補完

## 状態

| 項目 | ラベル |
|------|--------|
| 形式定義 | ADOPT CANDIDATE |
| 自動 Validator 連携 | NOT READY |
| LLM Context 生成 | UNKNOWN（将来候補のみ設計） |
