# Phase 1 Freeze — MCP Fetch Comparison

**Freeze date:** 2026-08-28  
**Authoritative Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`  
**Documentation:** `docs/ai_tool/mcp_comparison/`

Phase 1 を **ここで固定** する。以降の Phase 2 は別指示・別 Run が必要。

---

## 完了したこと

| 項目 | 証跡 |
|------|------|
| Local `read_url_text` 作成 | [tool_creation/READ_URL_COMPLETION_REPORT.md](../tool_creation/READ_URL_COMPLETION_REPORT.md) |
| Deterministic Test（mock / local server） | pytest `test_read_url_text.py` — 28 passed（2026-08-28 記録） |
| Real Web Smoke Test | Run `20260828_153616_read_url_real_web_smoke`（**別枠**） |
| MCP Fetch Comparison | Run `20260828_153335_mcp_fetch_comparison` — **14 cases** |
| 比較結果ドキュメント | 本ディレクトリ 9 ファイル |
| Safety / Failure / Limitations 記録 | 各 MD + Run JSON |

---

## 今回やっていないこと

- Agent 統合（`agent.py` 未変更）
- Registry 登録（`registry/tools.json` 未変更）
- MCP 本番接続 / allowlist
- MCP 自動選択・自動インストール・自動承認
- Tool 自動生成・自動実装
- 有料 API 利用
- 14 ケース Run の再実行・上書き
- 本番 Local Tool / MCP Provider / read_url 本体の変更

---

## Freeze 宣言

```text
MCP Fetch Comparison Phase 1
        ↓
14 cases（20260828_153335）結果を docs/ai_tool/mcp_comparison/ に固定
        ↓
STOP
```

### 凍結対象

- 14 ケースの数値・成否（`comparison.json` 準拠）
- Phase 1 hypotheses ラベル（H-MCP-1 … H-MCP-6）
- 「MCP 本番 ready ではない」「Local experimental のまま」の状態

### 凍結しないもの

- Local Tool の将来改善
- MCP SDK / server 版本更新
- Phase 2 設計検討（別 doc / 別 Run）

---

## 次に進む条件（将来 — 自動開始しない）

以下は **Phase 2 再開時** にのみ検討。Phase 1 Freeze では着手しない。

1. Trust model / Catalog 拡張の設計レビュー（Proposal レベル）
2. MCP Provider adapter（1.x schema / 2.x client 分離）の実装判断
3. Client-side URL policy を MCP 呼び出し前に適用するかの設計
4. Agent / Registry 統合の明示的 GO 判断（人間）

---

## 主要 Run 成果物（変更禁止）

```text
runs/ai_tool/20260828_153335_mcp_fetch_comparison/
├── inputs.json
├── comparison.json
├── outputs.json
├── safety_results.json
├── evaluation.json
├── audit.jsonl
├── REPORT.md
└── FAILURE_ANALYSIS.md
```

---

## 索引

| Doc | 用途 |
|-----|------|
| [README.md](./README.md) | 入口 |
| [CURRENT_STATUS.md](./CURRENT_STATUS.md) | 現在地 |
| [COMPARISON.md](./COMPARISON.md) | 14 case 表 |
| [EXPERIMENT_REPORT.md](./EXPERIMENT_REPORT.md) | 実験記録 |
| [PHASE1_FREEZE.md](./PHASE1_FREEZE.md) | 本ファイル |

---

## Local Tool 位置づけ（Freeze 時点）

```text
local:read_url_text
    ↓ experimental（Registry 未登録）
    ↓ MCP 比較材料取得済み
    ↓ 正式採用・read_file 置換 — 未決定・未着手
```
