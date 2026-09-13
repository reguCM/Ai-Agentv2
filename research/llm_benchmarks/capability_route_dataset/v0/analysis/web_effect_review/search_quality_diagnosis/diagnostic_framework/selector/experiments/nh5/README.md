# NH5 Experimental Selector

**目的:** NH1〜NH4 の experimental 知識を、問題指紋から診断手法・検証・エスカレーションへ **選択** できるか検証する。

## 本番との関係

| 対象 | 変更 |
|------|------|
| `selector/selector.py` | **変更しない** |
| `selector/rules.json` | **変更しない** |
| Agent / Tool / Manager | **変更しない** |
| 本実験 | `nh5_selector.py` + `rules.json` + `method_registry.json` |

## ファイル

- `nh5_selector.py` — `NH5Selector`（ルール + 本番 DiagnosticSelector 委譲）
- `rules.json` — always / feature_rules / hard_reject
- `method_registry.json` — 手法 ID → catalog status / hypothesis / runs

## 実行

```bash
python diagnostic_framework/run_nh5_selector_selection_experiment.py
```

出力: `runs/20260827_134500/nh5_selector_selection_experiment/`

## 禁止事項（実験ポリシー）

- 未検証手法を SUPPORTED/adopt として扱う
- experimental を確定仕様として扱う
- 新ルールの本番 `rules.json` への直接統合
- `auto_fix_allowed=true`

未知状況では UNKNOWN / ESCALATE / HUMAN_REVIEW を許容する。
