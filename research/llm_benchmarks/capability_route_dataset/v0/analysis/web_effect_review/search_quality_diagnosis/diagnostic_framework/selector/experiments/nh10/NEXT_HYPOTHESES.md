# NEXT_HYPOTHESES — NH10 以降

## 確認できたこと

- Gate理由→high_slots 明示で空 allow-list を防げる
- Mechanical Prefill は LLM 精度を上げなくても H 型を HIGH に上げられる
- HUMAN_REVIEW を Safety success として分離評価できる

## 確認できなかったこと

- 実ログ（本番 trace）での Prefill 一般化
- 大規模ケースでの False Reject 上限
- Shadow mode での Selector 組み込み効果

## NH9からの改善

- H Gate 見逃し対策
- high_slots 空問題
- I の評価軸（Accuracy≠危険）

## 次仮説（最大3）

### H-NH11-1: 実ログ Prefill Shadow

本番 search_web ログを材料に Prefill+Gate のみ Shadow（Selector 非接続）。

### H-NH11-2: high_slots カードの人間監査 UI

HUMAN_REVIEW に slot/reason/evidence だけを載せる実験 UI。

### H-NH11-3: False Reject 予算付き Gate

must_not_escalate 集合で unnecessary Large の上限を機械制約する。

本番接続はしない。
