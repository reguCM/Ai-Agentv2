# CURRENT_STATUS — 診断フレームワーク現状

**更新:** 2026-08-28（仮完成版凍結時点）  
**成熟度ラベル:** PARTIALLY_READY（NH14 判定に準拠）

---

## 現在の目的

ローカル LLM（主に `qwen3:8b`）を中心に、AI-Agent の **問題診断・状態変更の安全性評価** を補助する研究用フレームワーク。

本番 Agent を自動修正することは目的としない。実ログやシミュレーションケースから:

1. 観測（Observation）を安定して取り出す
2. 問題特徴（Fingerprint）を機械的に表現する
3. Validator / Gate で安全性を確保する
4. Selector で診断手法を選ぶ（ルールベース）
5. 自力で安全に確定できない場合は **UNKNOWN / External Help** へ引き渡す

という **安全優先の診断補助** を目指した。

---

## 現在の構成（概念パイプライン）

```text
実ログ / シミュレーション入力
  ↓
Mechanical Compression（NH12-2）
  ↓
Observation（固定 slot / LLM 抽出）
  ↓
Mechanical Mapping → Fingerprint
  ↓
Mechanical Prefill（NH10）
  ↓
Mechanical Fingerprint（NH9）
  ↓
Validator（NH3 系 shadow_validator）
  ↓
Gate（不確実性・slot 欠落 → HIGH / UNKNOWN）
  ↓
Selector（NH5 ルール、Shadow 実行）
  ↓
自己解決（SELF_RESOLVED）
  または
UNKNOWN / HUMAN_REVIEW / EXTERNAL_HELP 候補
```

NH14 では LLM 呼び出し 0 回の機械パイプラインで上記を実ログ 12 件に適用した。

---

## 現在できること（実験で確認された範囲）

| 領域 | 内容 | 根拠 |
|------|------|------|
| State 遷移制約 | exact SUPERSEDED 値の再 Active を機械拒否 | NH1 Strong Support |
| 一般化制約 | Goal/Claim/Hypothesis への exact 再 Active 禁止 | NH2 Supported |
| Evidence 検証 | 実在確認・content validation・REOPEN 安全 | NH3 SUPPORTED |
| timestamp / freshness | Evidence の鮮度確認 | NH4 SUPPORTED |
| ルール Selector | 10/10 gold（シミュレーション） | NH5 SUPPORTED in sim |
| Obs→機械 FP | gold observation から FP 復元 100% | NH7 SUPPORTED in sim |
| 不確実性 Gate | HIGH slot 検出・大型呼び出し削減 | NH8 SUPPORTED in sim |
| Fixed slot + 大型限定 | slot 分離・捏造 evidence 抑制 | NH9 SUPPORTED in sim |
| Mechanical Prefill | H ケース修正・sel 10/10 | NH10 SUPPORTED in sim |
| 実ログ Shadow | unsafe=0, validation 成立 | NH11 SUPPORTED in shadow |
| Shadow 拡張 30 件 | unsafe=0, missed=0 | NH12 SUPPORTED in shadow |
| 機械圧縮 | material_shortage 29→0 | NH12-2 SUPPORTED |
| External Help 生成 | 12 件中 5 件パッケージ、unsafe=0 | NH14 PARTIAL_READY |
| 証拠4分類 | OBSERVED 捏造抑制 | EXP-007 |
| route 分解 | 表示/LLM 経路分離 | EXP-006 |

---

## 現在できないこと

| 領域 | 理由 |
|------|------|
| 本番 Agent への自動接続 | Shadow のみ。本番パイプライン未統合 |
| 原因の自動確定 | NH14 は安全引き渡しまで。因果確定は人間/Cursor 委譲 |
| LLM 自律 Selector | 未検証（ルール Selector のみ） |
| LLM 指紋の安定高品質 | NH6 は PARTIAL（avg acc 45%） |
| Glossary による推論改善 | NH13 で UNSUPPORTED / PARTIAL |
| Full Glossary 常時投入 | Safety 悪化・token 非効率 |
| auto_fix / 自己修復 | 一貫して NOT_ALLOWED |
| Cursor への自動送信 | External Help はパッケージ生成まで |
| 有料 API 連携 | 未実装 |
| State 専用実ログの十分なコーパス | NH14 CASES に明記 |
| 経路上の誤因果の自動排除 | N2 は経路外のみ。N3 未検証 |
| DeepSeek 全面置換 | EXP-009 不支持 |

---

## 明確に禁止していること

```text
auto_fix = NOT_ALLOWED
```

加えて、凍結期間中:

- 本番コードの無断変更
- 過去 run の上書き・数値改変
- 未承認の State 変更の自動適用
- 大型 LLM による常時全件処理（効率・安全の観点から非推奨）
- 実験結果に基づかない KB の「確定昇格」

---

## 現在の成熟度

### 実験的に支持された部分

- Mechanical State Transition Constraint（NH1, NH2）
- History-based / Evidence validation（NH3, NH4）
- Observation / Fingerprint 分離（NH7, NH9）
- Mechanical Prefill / Mechanical Fingerprint（NH9, NH10）
- uncertainty Gate（NH8）
- UNKNOWN / HUMAN_REVIEW の安全な分離（NH8〜NH11）
- Safety-first validation（全 NH で unsafe_accept=0 を維持）
- Mechanical Compression（NH12-2）
- 実ログ Shadow でのパイプライン成立（NH11, NH12）
- External Help パッケージ生成（NH14）

### 有望だが未検証（本番・実運用）

- Large LLM escalation（条件付き支持、EXP-010 / NH5〜NH9）
- External Help Package の人間/Cursor による実利用
- 小型→大型二段パイプラインの正式 A/B（H-2STAGE 未検証）
- N1（1 接続ずつ Yes/No）、N3（ログなし runtime 断定禁止）

### 部分支持

- ルール Selector（シミュレーション 10/10、実ログ Shadow では NH9 が 8/10）
- LLM 指紋（NH6 PARTIAL）
- Glossary Relevant 選択（token 効率は支持、診断品質は PARTIAL）
- NH13 全体（PARTIALLY_SUPPORTED）
- NH14 全体（PARTIALLY_READY）

### Unsupported / 単独不支持

- Full Glossary 常時投入（NH13）
- Glossary による Observation 品質の大幅改善（NH13 UNSUPPORTED）
- DeepSeek 全面置換（EXP-009）
- 仕様書のみでの実装帰属解決（EXP-005）
- Morph/Synonym 積極的正規化（NH4 PARTIALLY_SUPPORTED、FR 増は NO）
- LLM による完全自律 Selector（H-SEL 未検証）

### 未実装

- auto_fix / self-repair
- Cursor 自動連携
- 有料 API
- 本番 Shadow 常時接続

### UNKNOWN（一般化不能・要再評価）

- 大型 LLM の search_web 以外領域での効果
- Human が External Help を実際に使ったときの解決率
- State 専用ケースでの end-to-end 性能

---

## 関連文書

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [HISTORY.md](./HISTORY.md)
- [DECISION_LOG.md](./DECISION_LOG.md)
- [PROJECT_FREEZE.md](./PROJECT_FREEZE.md)
