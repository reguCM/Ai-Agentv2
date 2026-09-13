# GLOSSARY_POLICY — 用語辞書の位置づけ

**対象:** `FW/knowledge_base/glossary/`  
**凍結日:** 2026-08-28

---

## 概要

診断フレームワーク用の用語・概念辞書を 3 層 + 機械 JSON で整備した（NH13 前）。NH13 / NH13-7 の結果を踏まえ、**最終方針** を以下に固定する。

---

## Human Glossary

**パス:** `glossary/human/GLOSSARY.md`

**方針:** 継続して利用・維持する。

日本語中心で開発・設計する人間が、以下を混同しないための資料:

- Observation / Fingerprint / Gate / Validator / Safety / Accuracy
- State / Claim / Hypothesis / Evidence / UNKNOWN

英単語の直訳ではなく、**本リポジトリでの役割** を説明する。

---

## Program Glossary

**パス:** `glossary/program/PROGRAM_GLOSSARY.md`

**方針:** 実装者が必要に応じて参照。維持する。

コード上の型名・フィールド名・モジュール境界との対応を記載。

---

## LLM Glossary

**パス:**

- `glossary/llm/LLM_CONTEXT_GLOSSARY.md` — 詳細版
- `glossary/llm/LLM_QUICK_REFERENCE.md` — 短縮版

**方針:** **常時投入しない。**

必要な場合のみ Relevant な項目を選択して渡す。

NH13 / NH13-7 の結論:

| 観点 | 結果 |
|------|------|
| 推論能力の直接改善 | **主要手段とは扱わない**（H-NH13-1 UNSUPPORTED） |
| Full 投入 | unsafe 増。非推奨 |
| Relevant / Mechanical 選択 | token 効率は支持（NH13-7-2 SUPPORTED） |
| 診断品質 | No Glossary とほぼ同等（NH13-7-3 PARTIAL） |

**推奨:** 機械選択（NH13-7 条件 D）または人手 curated Relevant。LLM による用語選択（条件 F）は recall 低・再現性に課題。

---

## 機械参照

**パス:** `glossary/glossary.json`（40 語、`build_glossary.py` 生成）

Selector 実験・機械 Glossary 選択で参照。本番 LLM プロンプトへの自動注入はしない。

---

## 人間向け記録との関係

| 領域 | 役割 |
|------|------|
| `docs/diagnostic_framework/` | 方針・意思決定（本書） |
| `glossary/human/` | 設計・レビュー時の参照 |
| `glossary/llm/` | 実験時の条件付きコンテキスト |
| `GLOSSARY_REPORT.md` | NH13 前の整備報告 |

---

## 関連

- [EXPERIMENT_SUMMARY.md](./EXPERIMENT_SUMMARY.md) §7-8
- FW/knowledge_base/glossary/GLOSSARY_REPORT.md
