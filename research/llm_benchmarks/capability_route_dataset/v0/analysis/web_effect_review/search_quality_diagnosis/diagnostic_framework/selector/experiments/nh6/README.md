# NH6 Experimental Fingerprint Generator

**目的:** 問題材料 → LLM 問題指紋生成 → NH5 Selector 接続の検証。

## 本番との関係

本番 Agent / Tool / Manager / Selector / search_web は**変更しない**。

## ファイル

- `feature_schema.json` — NH5 互換 feature キー定義
- `fingerprint_utils.py` — JSON 抽出・正規化・指紋評価

## 実行

```bash
python diagnostic_framework/run_nh6_fingerprint_selector_experiment.py
```

出力: `runs/20260827_140500/nh6_fingerprint_selector_experiment/`

## 条件

- **A:** Gold fingerprint → NH5 Selector（基準）
- **B:** LLM fingerprint → NH5 Selector
- **C:** LLM fingerprint + Evidence 4分類境界 → NH5 Selector
