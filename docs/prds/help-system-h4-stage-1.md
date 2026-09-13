# Help System H4 第一段階 — ファイル系 Tool 名依存の Help 解決

**状態:** H4-1 は H4 Core に包含。H4 Core は人間により **完了承認**（2026-09-08）。本ファイルは H4-1 範囲の正本のまま。H4 製品全体の完了ではない。独立 ToDo は [`help-system-h4-selection-core.md`](help-system-h4-selection-core.md)。

## Goals

Help System H2+H3 の次として、**H4 第一段階（H4-1）** だけを完了する。

対象は、ファイル観測要求がまだ個別 Tool 名 `read_file` に固定されている箇所を、Capability Index の `workspace_file_read` と Help 解決へ載せ替えること。H4 全体の完了ではない。

## Requirements

- [ ] `ChatTaskOrchestrator.required_capability()` のファイル系（`file` / `ファイル` / `repository`）は Tool 名 `read_file` ではなく capability id `workspace_file_read` を返す
- [ ] そのファイル系 Tool Gap 判定は `prefer_tool_for_capability("workspace_file_read")` で Tool 名を解決する。`fallback="read_file"` は使わない
- [ ] Help が Tool 名を返し、渡された Registry 行にその canonical name があるときだけ Tool Gap にしない
- [ ] Help が解決できないとき、`read_file` を推測して Gap 回避しない
- [ ] `build_tool_expectation()` は `"read_file" in tools` 判定と `fallback="read_file"` を使わない。Help 未解決、または解決名が渡された tools に無い場合は expectation を作らない
- [ ] `web` / `gpu` / `cpu` 分岐は現状どおり Tool 名を返す。Index に対応 capability が無いため Help 経路へ載せない
- [ ] `capability_resolution.py` は変更しない

## Non-Goals

- H4 全体の完了宣言
- `web` / `gpu` / `cpu` 用 capability を Index へ追加すること
- `task_runtime.detect_tool_gap()` の文字列突き合わせ仕様の変更
- `agent_turn.py` の `create_file` / `edit_file` Sandbox 注入の一般化（H4-1 では変更しない）

## H4 subsequent（H4-1 完了 ≠ H4 完了）

以下は **後続対象**。H4-1 の完了をもって H4 完了としない。

| 残件 | 場所 | 内容 |
|---|---|---|
| `web` / `gpu` / `cpu` → Tool 名 | `task_orchestration.required_capability()` | Capability Index に項目が無い。無理に Help へ載せない |
| `pending_capability_action()` の 3 Tool 許可 | `task_orchestration.py` | `{"read_file","search_files","list_files"}` |
| `observe_tool()` 内の `read_file` 固定 | `task_orchestration.py` | search hit 後の読取先 |
| `create_file` / `edit_file` 集合 | `task_orchestration.required_mutation_tool()` / `agent_turn.py` | Sandbox 注入を含む Domain 固有の可能性 |
| `_CAPABILITY_QUERIES` | `ai_tool/help/api.py` | capability → 固定検索語。Registry 非正本 |
| `_MINIMAL_TOOLS` / `next_capability_action()` | `capability_resolution.py` | 同根の Tool 名分岐。H4-1 ではファイルを変更しない |
| concept / requirement の Tool 名 hint | `concept_resolution.py` / `requirement_decomposition.py` | 同根。H4-1 範囲外 |

## Constraints

- 変更ファイルは H2H3 と同じ範囲に限定する: `ai_tool/help/**`（コメント記録のみ可）、`ai_tool/chat_interface/task_orchestration.py`。`agent_turn.py` は H4-1 要件を満たすなら無変更でよい
- Capability 正本は `registry/workspace_concepts.json` の `workspace_file_read.tools`
- `detect_tool_gap()` は `required_capability` 文字列を Registry の name/description/keywords に含むかで判定する（`tools/ai/task_runtime.py`）。H4-1 ではこの関数を変更しない。ファイル系は呼び出し側で Help 解決名と渡された Registry 行を照合する
- Generation-Time Assumption Check: 正本にある Tool 名を別 allowlist へ複製しない。`fallback="read_file"` はその複製だった

## Approach

1. `required_capability()` のファイル系だけ capability id を返す。他分岐は残件として残す
2. `detect_required_tool_gap()` はファイル系だけ Help 確認名と渡された Registry 行を照合する。確認手順は (1) `prefer_tool_for_capability`（fallback なし）(2) 未解決なら Capability Index の `tools` を `describe` / `local:<name>` で確認。未確認なら `detect_tool_gap(required_capability="workspace_file_read", candidate_tool=解決名 or None)`。`web` / `gpu` / `cpu` は既存どおり Tool 名を needle にする
3. `build_tool_expectation()` は同じ確認名が tools にあるときだけ expectation を生成する
4. 既存テスト `test_31` の `gap.required_capability == "read_file"` は `workspace_file_read` へ更新する。`test_32` は `read_file` 行があるとき Gap なしのまま

### 検討して採用しなかった案

- `web` / `gpu` / `cpu` も今 Help 検索する — Index に capability が無く、Tool 名推測が残る
- `capability_resolution.py` を同時修正する — 同根だが H4-1 の範囲外
- `task_runtime.detect_tool_gap()` を capability id 対応にする — Runtime 契約変更であり H4-1 ではない

## Open Questions

なし（H4-1 完了条件は確定済み。後続は上表）

## Discoveries

- 2026-09-08 H4-1: `prefer_tool_for_capability("workspace_file_read")` は検索語 `read file` のため 0 件。`describe("read_file")` は未ヒット、`describe("local:read_file")` はヒット。Index `workspace_file_read.tools` を候補にし、Help describe で agent-available を確認する。`fallback="read_file"` による推測ではない。`_CAPABILITY_QUERIES` 自体の一般化は後続。

## Ambiguity Report

```
Ambiguity Report:
  Goals:        0.0   ✓ clear
  Acceptance:   0.0   ✓ clear
  Boundaries:   0.0   ✓ clear
  Alternatives: 0.25  ✓ considered
  Assumptions:  0.25  ✓ detect_tool_gap needle is observed, not changed
  ──────────────────────────────
  Aggregate:    0.10  ✓ below threshold (0.2 spec)
```

Caller: write-prd Phase 5 / grill-me spec mode. Threshold 0.2. Gate pass.
