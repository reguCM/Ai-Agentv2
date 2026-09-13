# AI-Agent Project Audit — Phase 1

**監査日:** 2026-08-28  
**目的:** プロジェクト横断の現在地棚卸し（**新規実装・実験なし**）

## この監査で分かること

- **AI-Agent として実際に動作するもの**（Agent Core + Registry 経由）
- **experimental だが Agent 未統合のもの**（`ai_tool/` 層）
- **設計・文書のみのもの**
- **未着手 / NOT READY のもの**

## 判定ルール（要約）

```text
ファイルが存在する        ≠ 機能が完成
テストが通る              ≠ Agent から使える
Experimental Tool がある  ≠ Production Tool
MCP Provider がある       ≠ Agent が MCP を使える
```

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [CURRENT_STATE.md](./CURRENT_STATE.md) | 現在地（1 枚） |
| [ARCHITECTURE_MAP.md](./ARCHITECTURE_MAP.md) | 全体構造・依存関係 |
| [COMPONENT_STATUS.md](./COMPONENT_STATUS.md) | 主要コンポーネント表 |
| [TOOL_STATUS.md](./TOOL_STATUS.md) | Tool 別ステータス |
| [PRODUCTION_VS_EXPERIMENTAL.md](./PRODUCTION_VS_EXPERIMENTAL.md) | 本番 / 実験境界 |
| [CURSOR_VS_AGENT.md](./CURSOR_VS_AGENT.md) | Cursor と AI-Agent の役割分離 |
| [COMPLETED_CAPABILITIES.md](./COMPLETED_CAPABILITIES.md) | 現在できること |
| [KNOWN_GAPS.md](./KNOWN_GAPS.md) | 未完成・ギャップ |
| [NEXT_DECISIONS.md](./NEXT_DECISIONS.md) | 判断候補（優先順位は人間） |
| [AUDIT_REPORT.md](./AUDIT_REPORT.md) | 最終報告 |
| [LEGACY_TOOL_AUDIT.md](./LEGACY_TOOL_AUDIT.md) | Legacy GPU/CPU Tool 監査（Phase 1 — 修正なし） |
| [AGENT_TOOLCALLING_AUDIT.md](./AGENT_TOOLCALLING_AUDIT.md) | Agent ↔ LLM Tool Calling 横断監査 |
| [OBSERVATION_TOOL_MATRIX.md](./OBSERVATION_TOOL_MATRIX.md) | GPU/CPU Observation capability matrix |
| [SPEC_DRIFT_ANALYSIS.md](./SPEC_DRIFT_ANALYSIS.md) | Specification drift 分析 |
| [OBSERVATION_CAPABILITY_AUDIT.md](./OBSERVATION_CAPABILITY_AUDIT.md) | GPU/CPU 能力境界監査 |
| [OBSERVATION_TOOL_DESIGN.md](./OBSERVATION_TOOL_DESIGN.md) | Tool 責務・改訂案（Phase 1 設計） |
| [OBSERVATION_SPEC_HUMAN_REVIEW.md](./OBSERVATION_SPEC_HUMAN_REVIEW.md) | v2 仕様ドラフト — Human Review パッケージ（Phase 2） |
| [WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md) | Web Research → TDA 拡張 — Phase A 調査 |
| [WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_POC.md](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_POC.md) | Tool Development Assistance — Phase B PoC |
| [TOOL_DEVELOPMENT_ASSISTANCE_CAPABILITY_DISCOVERY.md](./TOOL_DEVELOPMENT_ASSISTANCE_CAPABILITY_DISCOVERY.md) | TDA Capability Discovery — Phase C 観測 |
| [TOOL_DEVELOPMENT_ASSISTANCE_PRACTICAL_DECISION_SUPPORT.md](./TOOL_DEVELOPMENT_ASSISTANCE_PRACTICAL_DECISION_SUPPORT.md) | TDA Practical Decision Support — Phase D 実測 |
| [TOOL_DEVELOPMENT_ASSISTANCE_RESEARCH_REUSE.md](./TOOL_DEVELOPMENT_ASSISTANCE_RESEARCH_REUSE.md) | TDA Research Reuse & Hierarchical Discovery — Phase E |
| [TDA_STANDARD_WORKFLOW_ADOPTION.md](./TDA_STANDARD_WORKFLOW_ADOPTION.md) | TDA Standard Workflow Adoption — Phase F Operating Model |
| [TDA_REAL_WORLD_AMBIGUOUS_EVALUATION.md](./TDA_REAL_WORLD_AMBIGUOUS_EVALUATION.md) | TDA Real-World Ambiguous Evaluation — Phase G |
| [TDA_RELEVANT_FACET_ROUTING_INTEGRATION.md](./TDA_RELEVANT_FACET_ROUTING_INTEGRATION.md) | TDA Relevant Facet Routing Integration — Phase M |
| [TDA_REQUIREMENT_DRIVEN_FACET_DISCOVERY.md](./TDA_REQUIREMENT_DRIVEN_FACET_DISCOVERY.md) | TDA Requirement-driven Facet Discovery — Phase N |
| [TDA_GENERALIZED_FACET_DISCOVERY.md](./TDA_GENERALIZED_FACET_DISCOVERY.md) | TDA Generalized Facet Discovery — Phase N+1 |
| [UR_PROGRAM_VALIDATOR_URSIM_POC.md](./UR_PROGRAM_VALIDATOR_URSIM_POC.md) | URScript Validator + URSim Boundary — Phase H |
| [UR_PROGRAM_VALIDATOR_LIVE_PHASE_I.md](./UR_PROGRAM_VALIDATOR_LIVE_PHASE_I.md) | Live URSim + Tool Development Loop — Phase I |
| [UR_PROGRAM_VALIDATOR_PHASE_I_R.md](./UR_PROGRAM_VALIDATOR_PHASE_I_R.md) | URSim Environment Recovery — Phase I-R |
| [UR_PROGRAM_VALIDATOR_PHASE_I_R_B_PREFLIGHT.md](./UR_PROGRAM_VALIDATOR_PHASE_I_R_B_PREFLIGHT.md) | WSL2 + Docker Preflight — Phase I-R-B |
| [UR_PROGRAM_VALIDATOR_PHASE_I_R_B_PROGRESS.md](./UR_PROGRAM_VALIDATOR_PHASE_I_R_B_PROGRESS.md) | Phase I-R-B Progress (post WSL install) |
| [STORAGE_POLICY_PHASE_I_R_B.md](./STORAGE_POLICY_PHASE_I_R_B.md) | Storage Policy — C/D placement baseline |

## Phase 2 成果物

| 種別 | パス |
|------|------|
| v2 spec drafts | `docs/ai_tool/tool_creation/specs/*_v2_draft.json` |
| Capability matrix | [OBSERVATION_CAPABILITY_MATRIX.md](../tool_creation/OBSERVATION_CAPABILITY_MATRIX.md) |
| Validator tests | `tests/ai_tool/tool_creation/test_observation_spec_v2_draft.py` |
| Run script | `ai_tool/run_observation_spec_phase2.py` |

## 関連（監査対象外だが参照）

| 領域 | 入口 |
|------|------|
| AI-TOOL Layer | [../README.md](../README.md) |
| Tool Creation | [../tool_creation/README.md](../tool_creation/README.md) |
| MCP Comparison（FROZEN） | [../mcp_comparison/README.md](../mcp_comparison/README.md) |
| Diagnostic Framework（FROZEN） | [../../diagnostic_framework/README.md](../../diagnostic_framework/README.md) |
| Agent 仕様 | [../../PROJECT_SPEC.md](../../PROJECT_SPEC.md) |

## 制約（本監査）

- `agent.py`, `tools/`, `registry/tools.json` — **未変更**
- 新規実験・Agent 統合 — **未実施**
- 既存 Run — **未変更**
