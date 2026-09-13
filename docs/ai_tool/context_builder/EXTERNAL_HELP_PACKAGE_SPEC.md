# External Help Package — Specification (Phase 2)

**状態:** EXPERIMENTAL  
**Component:** `ai_tool.context_builder.package_generator`

## 目的

Phase 1 Context Builder の出力を、Cursor / 大型 LLM / 人間へ引き渡せる **External Help Package** として整理する。

**Package は実装依頼ではない。** 分かっている事実と不足情報を分離して渡す。

## 入力

```json
{
  "tool_id": "local:workspace_read_text_scoped",
  "output_dir": "runs/ai_tool/<run>/external_help_packages/local_workspace_read_text_scoped"
}
```

Phase 1 と同様、`build_tool_development_context()` を内部で呼ぶ。

## 出力ディレクトリ構造

```text
external_help_package/
├── request.json              # 制約・readiness（NH14 request.json 思想）
├── SUMMARY.md                # 人間向け概要
├── CONTEXT_MANIFEST.json     # Manifest + selected_files + audit（本文と分離）
├── SPECIFICATION.md
├── CONTRACT.md
├── IMPLEMENTATION_CONTEXT.md
├── TEST_CONTEXT.md
├── SAFETY_CONTEXT.md
├── CHANGE_POLICY.md
├── CATALOG_CONTEXT.md
├── KNOWN_LIMITATIONS.md
├── RELATED_CONTEXT.md
└── UNKNOWN_AND_MISSING.md    # UNKNOWN / REFERENCE_ONLY / EXCLUDED 集約
```

Phase 1 の `selected_context/` フラット配置とは**別レイアウト**（スロット別 Markdown + 集約 Manifest）。

## Readiness（Phase 1 状態との対応）

| Package readiness | Phase 1 status | 条件 |
|-------------------|----------------|------|
| `READY` | `OK` | P0 slot 欠落なし |
| `PARTIAL` | `PARTIAL` | P0 に UNKNOWN |
| `NOT_READY` | `ERROR` | tool_id 未解決等 |

新規状態体系は作らない。上記マッピングのみ。

## Slot ファイル形式

各 `*.md` は Manifest セクション + Body セクション:

```markdown
# Specification

**Slot:** specification
**Priority:** P0
**Status:** FOUND | UNKNOWN | REFERENCE_ONLY | EXCLUDED
**Trust:** fetched | metadata_only | not_available

## Sources
| path | reason | content_status |

## Body
（allowlist 内 fetched 本文のみ。REFERENCE_ONLY は本文なし）
```

## Safety

- Phase 1 Scoped Read 経由のみ本文取得
- `tools/` 等 allowlist 外は **REFERENCE_ONLY メタデータのみ**
- sensitive path 除外
- UNKNOWN 捏造禁止
- Glossary 大量投入なし

## NH14 との関係

| NH14 | Tool Development EHP |
|------|----------------------|
| OBSERVATION.json | CONTEXT_MANIFEST.json + slot status |
| CODE_CONTEXT/ | IMPLEMENTATION_CONTEXT.md（参照のみ） |
| SUMMARY.md | SUMMARY.md（事実/不明の分離） |
| request.json constraints | 同思想 |

診断 FW パイプラインは呼ばない。

## 参照

- [CONTEXT_BUILDER_SPEC.md](./CONTEXT_BUILDER_SPEC.md)
- [PHASE2_OVERLAP_ANALYSIS.md](./PHASE2_OVERLAP_ANALYSIS.md)
