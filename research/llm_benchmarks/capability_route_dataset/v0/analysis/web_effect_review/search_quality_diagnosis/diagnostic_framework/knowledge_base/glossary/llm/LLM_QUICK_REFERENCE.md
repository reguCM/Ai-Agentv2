# LLM_QUICK_REFERENCE — 短縮コンテキスト

LLM プロンプトの先頭に付与する想定の短い参照。詳細は `LLM_CONTEXT_GLOSSARY.md`。

---

## このプロジェクトでの意味

| 英語 | 日本語 | 一言 |
|------|--------|------|
| Observation | 観測 | 材料から読み取った事実（fixed slots） |
| Fingerprint | 問題指紋 | Observation→機械 Mapping の features |
| Evidence | 証拠 | 4分類ラベル / State オブジェクト / slot 引用 |
| Selector | 選択器 | features→診断手法（機械、LLM ではない） |
| Gate | ゲート | Large/HUMAN エスカレーションの機械判断 |
| Validator | 検証器 | 安全・State 遷移の機械検証 |
| HUMAN_REVIEW | 人間確認 | 安全停止（失敗ではない） |
| Small LLM | 小型LLM | Observation slot 抽出 |
| Large LLM | 大型LLM | HIGH slot 訂正のみ |
| Mechanical Mapping | 機械マッピング | slots→features（LLM 禁止） |
| Mechanical Prefill | 機械プリフィル | 材料から slot ルール補完 |
| Mechanical Compression | 機械圧縮 | ログ→compression slots（NH12-2） |

---

## パイプライン（experimental）

```text
材料 → [Compression] → [Prefill] → Observation(slots) → Mapping → Fingerprint
     → Gate → [Large LLM] → Validator → Selector → [HUMAN_REVIEW]
```

本番 Agent 未接続。実験 Shadow のみ。

---

## LLM が守ること

1. **Observation を推測しすぎない** — 材料に無ければ UNKNOWN
2. **Fingerprint を勝手に作らない** — Mapping は機械側
3. **Evidence を捏造しない**
4. **UNKNOWN を無理に解消しない**
5. **Gate / Selector / Validator の判断を代替しない**
6. **本番修正を勝手に実行しない**
7. **stdout の件数表示を信じすぎない** — handoff JSON を見る

---

## よくある混同

- Observation ≠ Fingerprint
- Evidence ≠ Observation
- OBSERVED（4分類）≠ OBSERVED（slot status）
- Gate ≠ Validator
- Selector ≠ Validator
- Safety ≠ Accuracy
- SUPPORTED（実験）≠ adopt（採用）≠ ACTIVE（State）
- stdout ≠ LLM handoff
- exists（件数）≠ content（snippet 中身）

---

## status 語彙の分離

| 種類 | 値の例 |
|------|--------|
| slot / Gate 不確実性 | OBSERVED, NOT_OBSERVED, UNKNOWN, HIGH, LOW |
| State ライフサイクル | ACTIVE, SUPERSEDED, REOPEN |
| 仮説・実験評価 | SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED |
| 採用レベル | adopt, experimental, unknown |

同じ「status」という語で全部を混ぜない。

---

## Large LLM の範囲（NH9-10）

- **やる:** HIGH と判定された slot の訂正
- **やらない:** 全診断、Fingerprint 生成、Gate 判断、本番 fix

---

## 参照

- 詳細: `LLM_CONTEXT_GLOSSARY.md`
- 機械可読: `../glossary.json`
- 実験索引: `../../EXPERIMENT_INDEX.md`
