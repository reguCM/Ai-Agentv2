# Tool 診断フレームワーク（汎用 / 記録・観測・分析のみ）

このディレクトリ配下には「対象 Tool のコード＋実測ログ（または観測データ）」を LLM に読ませ、
原因候補を **自力で** 仮説化・整理させるためのフレームワークを追加します。

## 重要（制約）

- 対象 Tool の実装・既存パイプライン・heuristic・ranking・Gate・Stage3/4 は変更しません
- 出力は追加ファイルのみ（既存ログ/既存データは破壊しません）
- LLMに事前結論（例: 「Cが原因」）を与えません

## 起動

例（search_web 用プロファイル）:

```text
python run_tool_diagnosis.py --profile profiles/search_web.yaml --mode evidence_only
```

LLM 解析まで実行する場合:

```text
python run_tool_diagnosis.py --profile profiles/search_web.yaml --mode full
```

## 設計

- 汎用化の核: `profiles/<tool>.yaml` で
  - 読ませるコード抜粋（ファイル/行レンジ）
  - 実測ログ（ケース群）の読み込み方式
  - 原因候補ラベル（A〜など）
  - LLMに渡す診断質問
  を差し替えます
- フレームワーク本体は、特定Tool（search_web）に固定しません

## 出力

`runs/<diagnostic_run_id>/` に以下を生成します:

- `CODE_ANALYSIS.md`（コード読解）
- `CASE_ANALYSIS.md`（ケース別）
- `LLM_DIAGNOSIS.md`（統合）
- `llm_diagnosis.json` / `llm_diagnosis.csv`
- `HUMAN_DECISION_SHEET.md`（人間用記入欄）

