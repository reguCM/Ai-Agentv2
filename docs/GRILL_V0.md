# Grill v0 — 人間向け質問原則と出口

**内部ID:** `grill_human_v0`
**状態:** 仮仕様 v0 / 実験前
**記録日:** 2026-09-09

Human Grill の原則と出口だけを固定する。Technical Grill は別工程。Human Grill の実験環境はまだ無い。

Technical Grill / System First の観察コードは `research/grill_observation_v0/` にある。本ファイルの代替でも Production 統合でもない。詳細は `docs/SYSTEM_ASSET_INDEX.md` の Grill観察研究。

---

## 質問原則

- 未決定事項を一律に質問しない
- 人間の意図が必要なものを優先する
- Goal Tree 上位ほど後戻り影響が大きいとして優先する
- 複数枝へ横断影響するものも優先する
- 技術詳細・末端 Decision は原則 AI 側へ任せる
- 上位 Decision への回答後、残り Decision を再評価する
- 深い技術 Decision でも横断影響が大きい場合は重要扱いする
- ただし人間の意図が不要なら Human 質問ではなく AI REVIEW 側へ回す

---

## Grill 出口

Human Grill は、「未決定事項がゼロ」になったら終了ではない。

以下が成立した時点を出口とする。

- 何を作りたいかが明確
- 完成時に何ができれば成功か分かる
- 人間の意図が必要な上位・横断 Decision が解決済み
- 残った未決定事項が主にコード設計・技術判断として AI へ委任可能

つまり、**人間が決める必要のある未決定事項 = 0** になった地点で Human Grill を終了し、Human Specification / Goal Contract 側へ渡す。

この後の Technical Grill は別工程として扱う。

---

## 境界

- 仮仕様 v0。Human Grill 実験前。汎用保証ではない
- Production 未統合
- 既存 Skill `grill-me` の代替実装ではない。人間向け原則の記録である
- `research/grill_observation_v0/` の観察研究を、本正本の実装済み状態とはしない
