# DIAGNOSTIC_WORKFLOW

**現時点の仮案。** 実装された自動パイプラインではない。

```text
Tool異常の疑い
 ↓
機械的観測（件数、snippet空、ranking脱落、backend 等）
 ↓
ログの有無確認
 ↓
FACT / OBSERVED / INFERENCE / UNKNOWN の整理（常時）
 ↓
対象範囲判定（検索本体 / Agent handoff / ハーネスのみ 等）
 ↓
必要ならコード route 分解（表示と LLM を分離）
 ↓
必要なら collect と ranking を別パック
 ↓
必要なら仕様書（地図のみ・行番号なし）
 ↓
小型LLMによる局所解析・一次候補
 ↓
複数候補の保持（早期に消しすぎない）
 ↓
経路外疑い → N2 存在ゲート（YES≠原因）
 ↓
ログなし runtime → N3（断定禁止／UNKNOWN）※仮説
 ↓
全体統合が必要 → 大型LLMエスカレーション
 ↓
追加調査リスト（API生応答、messages 中身の確認等）
 ↓
人間確認
 ↓
修正提案（未承認では実行しない）
 ↓
テスト設計
 ↓
再診断
```

### ガードレール（実験から）

1. `existence_status=YES` を原因の強さに使わない  
2. stdout 要約を LLM 入力と同一視しない  
3. 診断ハーネス専用コードを本番経路に混ぜない  
4. auto_fix は証拠不足なら `NOT_ALLOWED` / `NEEDS_MORE_EVIDENCE`  
