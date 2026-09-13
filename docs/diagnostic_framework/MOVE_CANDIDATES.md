# MOVE_CANDIDATES — AI-Agent 直下ファイルの整理候補

**調査日:** 2026-08-28  
**更新:** 2026-08-28 — Phase/KSS ベンチを `research/benchmarks/` へ移動済み

---

## 実施済み（2026-08-28）

AI-Agent 直下にあった研究・ベンチマーク用ファイルを **`research/benchmarks/`** へ移動した。

| 移動元 | 移動先 | 件数 |
|--------|--------|------|
| `_phase*` + log/json | `research/benchmarks/phases/phase1/` 〜 `phase5/` | 約 30 |
| `_kss*` | `research/benchmarks/kss/` | 6 |
| `_knowledge_source_observe_bench.py` | `research/benchmarks/observe/` | 1 |
| `_debug_*` | `research/benchmarks/debug/` | 9 |
| `_verify_*` | `research/benchmarks/verify/` | 2 |
| `_phase_a_query_smoke.py` | `research/benchmarks/smoke/` | 1 |

- 各スクリプトは `common_paths.REPO_ROOT` でリポジトリルートを参照（`cwd`・`PYTHONPATH` は従来どおりルート基準）
- phase 間の summary JSON 参照は `HERE` / 相対パスに更新済み
- 詳細: [research/benchmarks/README.md](../../research/benchmarks/README.md)

**AI-Agent 直下に残したもの:** `agent.py`, `PROJECT_SPEC.md`, `registry_test.py`, `test_ollama.py`（本番・汎用テスト）

---

## 診断フレームワーク実体（移動不要）

| 現在位置 | 移動してよいか |
|----------|---------------|
| `research/llm_benchmarks/.../diagnostic_framework/` | **いいえ** — 正しい配置 |

---

## 本番・プロジェクト根幹（移動しない）

| ファイル | 理由 |
|----------|------|
| `agent.py` | 本番 Agent |
| `PROJECT_SPEC.md` | プロジェクト全体仕様 |
| `registry/`, `tools/`, `tests/` | 本番実装 |

---

## 将来の整理候補（未実施）

| 現在位置 | 候補 | 備考 |
|----------|------|------|
| `registry_test.py` | `tests/` | 参照確認後 |
| `test_ollama.py` | `tests/` | 参照確認後 |

---

## docs/ との関係

| パス | 役割 |
|------|------|
| `docs/diagnostic_framework/` | 診断 FW 仮完成記録（NH 系） |
| `docs/kss*.md` | KSS 設計メモ（ベンチは `research/benchmarks/kss/`） |
| `docs/architecture.md` | 本番アーキテクチャ |

統合しない。役割が異なる。

---

## 関連

- [FREEZE_REPORT.md](./FREEZE_REPORT.md)
- [INDEX.md](./INDEX.md)
