# Tool Registry CHANGELOG

`registry/tools.json` の変更履歴。大規模 CMS は目指さない。  
**形式:** 日付 / 変更内容 / 理由

---

## 2026-09-08 — get_gpu_status に「状態」

- **変更:** `get_gpu_status.keywords` に `状態` を追加
- **理由:** H4 Q4（汎用 GPU → `gpu_device_observation`）。`状態` が `cpu_status` のみにあると exclusive 扱いになり、「gpu の状態を確認する」が `cpu_observation` を拾う。除外表は Q40 で GPU に広げない。語彙正本の Registry で横断共有にし、Q36 / Q43 で device に収束させる。

---

## 2026-09-02 — P2-3 search_files Agent 公開

- **追加:** `search_files` を `registry/tools.json` へ登録（`visibility: agent`）
- **実装:** 既存 `tools/file/workspace/search_files.py` を正規経路へ接続（新規実装なし）
- **Input:** `query`（必須）, `path`（任意）のみ公開。`glob` / 正規表現は Schema 非公開
- **検索:** 部分文字列一致、指定 path 以下を再帰走査（`list_files` とは異なる）
- **Security:** P2-1 / P2-2 と同じ workspace 境界（`_paths.py`）
- **理由:** Workspace 内のコード・テキストから文字列を安全に検索する最小能力を追加

---

## 2026-09-02 — P2-2 list_files Agent 公開

- **追加:** `list_files` を `registry/tools.json` へ登録（`visibility: agent`）
- **実装:** 既存 `tools/file/workspace/list_files.py` を正規経路へ接続（新規実装なし）
- **Input:** `path` のみ公開（`recursive` / `glob` は Schema 非公開、既定は非再帰・直下のみ）
- **Security:** P2-1 と同じ workspace 境界（`_paths.py`）
- **未公開:** `search_files`（P2-3）
- **理由:** Agent が Workspace 内のディレクトリ構成を安全に確認できる最小探索能力を追加

---

## 2026-09-02 — P2-1 read_file Agent 公開

- **追加:** `read_file` を `registry/tools.json` へ登録（`visibility: agent`）
- **実装:** 既存 `tools/file/workspace/read_file.py` を正規経路へ接続（新規実装なし）
- **Security:** workspace root 固定（リポジトリ root）、`..` 拒否、`relative_to` による境界チェック、read-only、64KB 上限
- **変更:** `_paths.py` の workspace 外エラーから内部 root 絶対パスを除去（LLM 露出抑制）
- **未公開:** `list_files`, `search_files`（P2-2 / P2-3）
- **理由:** Agent の Workspace 内 read-only ファイル読取を Native Tool Calling 経路で安全に提供

---

## 2026-09-02 — P1-2 Tool Calling 規約整備

- **追加:** `docs/TOOL_CALLING_RULES.md`（Tool Contract 規約正本）
- **追加:** `tools/system/tool_contract.py`（規約検証・参照ヘルパ）
- **追加:** `tests/test_tool_calling_rules.py`（規約・経路の最小テスト）
- **変更なし:** `registry/tools.json` の Tool 定義本体（全面改修は行わない）
- **理由:** Tool Calling 主経路の品質基準を明文化し、実装が規約から乖離しすぎない最小検証を入れる

---

## 2026-09-02 以前（P0 までの主要経緯・要約）

| 時期 | 変更 | 理由 |
|------|------|------|
| P0 | `read_url_text` を Registry 正本（`visibility: agent`）へ | Native TC 主経路の単一正本化 |
| P0 | `active_model` を `qwen3_14b` へ（暫定） | Tool Calling 対応モデルとの整合 |
| 採用 | `get_gpu_status`, `get_gpu_processes`, `get_cpu_status` 等を agent 公開 | 観測 Tool の実測化 |
| 意図的 | Tool Builder 系は `visibility` 未指定 | LLM から直接呼ばせずパイプライン内部で使用 |

詳細な過去パッチは git 履歴および `runs/ai_tool/` 配下の採用記録を参照。
