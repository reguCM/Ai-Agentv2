# Observation Tool Implementation — Phase 1

**Date:** 2026-08-28  
**Scope:** Windows + NVIDIA GPU + CIM CPU（現在環境のみ）

## 実装内容

| Tool | 変更 |
|------|------|
| `get_gpu_status` | nvidia-smi 実測（FIXED_STUB 廃止） |
| `get_gpu_processes` | 維持（82c40db 契約） |
| `get_cpu_status` | **新規** — Win32_Processor CIM |
| `cpu_status` | Legacy `{status}` 互換維持 |

## Registry（selective）

Agent visibility = `get_gpu_status`, `get_gpu_processes`, `cpu_status`, `get_cpu_status` のみ。  
未承認 Tool（search_web 等）は HEAD 基準で採用していない。

## Agent

- System Prompt: observed/unknown/unsupported/unavailable ルール（1 箇所）
- 起動時 `[AGENT_TOOL_CALLING_CAPABILITY]` 診断（モデル名ハードコードなし）

## Run

`python ai_tool/run_observation_implementation_phase1.py`

## Human Review 適用

HR-1, HR-2, HR-4, HR-5, HR-6, HR-7 — 実装済み  
HR-3 gpu_uuid — 未実施（承認どおり）
