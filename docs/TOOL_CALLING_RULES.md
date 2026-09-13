# Tool Calling 規約（Tool Contract）

**TASK_ID:** `TOOL-CALLING-RULES-P1`  
**正本:** 本ドキュメント（運用規約） + `registry/tools.json`（登録データ）  
**関連:** `registry/TOOLS_CHANGELOG.md`, `tools/system/tool_contract.py`

---

## 1. Tool とは何か

AI-Agent における **Tool** は、単なる Python 関数ではない。  
LLM（Native Tool Calling）が選択し、Agent が実行し、結果を LLM へ返す **契約付き能力単位** である。

正規経路:

```text
registry/tools.json
    ↓
create_ollama_tools()  （visibility=agent のみ LLM 公開）
    ↓
Ollama Native Tool Calling
    ↓
execute_tool()
    ↓
実装（module.function）
    ↓
結果を messages（role=tool）へ JSON 返却
```

Registry に登録されていない Tool を Agent 向けとして暗黙公開しない。  
`production_bridge` overlay は P0 以降 **空**（`read_url_text` は Registry 正本）。

---

## 2. Tool Contract

各 Tool は次の観点で定義する。すべてを JSON の必須フィールドにする必要はないが、**新規 Tool は意識的に埋める**。

| 観点 | Registry / 実装での表現 |
|------|-------------------------|
| **identity** | `name`（tool_id）, `module`, `function` |
| **purpose** | `description`, `keywords`, `category` / `subcategory` |
| **input** | `input`（引数 Schema）, 任意で `required` |
| **output** | 実装の戻り値。Registry の `output` はヒント（任意） |
| **error** | 実装が返す `ok` / `status` / `error` 等 |
| **side_effect** | 規約上 `side_effect` フィールド（新規推奨）。未記載は実装・description から推定 |
| **security** | `risk` + 実装制約（SSRF 等） |
| **visibility** | `agent` / 未指定（非公開）/ 将来 `pipeline` 等 |

**原則:** LLM が推測しなくてよい情報は Registry の Schema と description に書く。  
**原則:** 「Registry に true とあるから動く」ではない。`verified` 相当の実測は別途（Model Registry と同様の思想）。

---

## 3. Tool ID

### 3.1 命名規則（新規 Tool）

- **形式:** `snake_case`（小文字・数字・アンダースココア）
- **正規表現:** `^[a-z][a-z0-9_]*$`
- **例:** `get_gpu_status`, `read_url_text`, `search_web`
- **禁止（新規）:** ハイフン、ドット、CamelCase、空白、日本語 ID

### 3.2 既存 Tool

- **既存 ID は今回の作業で改名しない。** 互換性優先。
- Legacy 例: `cpu_status`（構造化版は `get_cpu_status` として別 ID で共存）

### 3.3 deprecated Tool

- 廃止予定の Tool は Registry で `status: deprecated`（将来フィールド）または CHANGELOG で明示。
- ID 変更ではなく、visibility を外し、後継 Tool を案内する。

---

## 4. description 規則

description は **LLM が Tool を選ぶための一次情報** である。人間向けの一言だけにしない。

### 4.1 含めるべき内容

1. **何をするか**（対象・データ源・操作種別）
2. **いつ使うか**（他 Tool との使い分け）
3. **何を返すか**（主要フィールド・失敗時の扱い）
4. **重要な制約**（read-only、実行しない、フォールバックしない 等）

### 4.2 良い例（既存）

```text
GPUの基本状態を取得する。GPUモデル、温度、使用率、VRAM使用量を nvidia-smi から実測する。
取得不能時は unknown/unavailable を返し固定値へフォールバックしない。
```

```text
既知の HTTP/HTTPS URL から本文を read-only GET で取得する（Fetch / Evidence）。
main_text と quality（fact_ready 等）を返す。意味推論・要約は行わない。
URLが分からない探索はsearch_web。
```

### 4.3 禁止・非推奨（単独では不十分）

次のみの説明は **新規 Tool では禁止**:

- 「情報を取得します」
- 「処理を実行します」
- 「データを確認します」

### 4.4 長さ

必要な制約は書くが、冗長な繰り返しは避ける。`keywords` で補助してよい。

---

## 5. Input Schema 規則

Registry の `input` は Ollama / OpenAI 互換の function parameters に変換される（`agent.create_ollama_tools`）。

### 5.1 各引数に持たせるもの

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `type` | **はい** | `string`, `integer`, `number`, `boolean`, `object`, `array` |
| `description` | **はい**（引数がある場合） | LLM 向け。単位・形式・例を簡潔に |
| `required` | 任意 | `true` のとき parameters.required へ |

トップレベル `required: ["arg1"]` もサポート（レガシー互換）。

### 5.2 表現すべき制約

必要なら Schema に書く:

- 必須 / 任意 / デフォルト（description に「省略時は…」）
- 許可値・範囲（`enum`, `minimum` / `maximum` は JSON Schema 互換で可）
- 形式（URL、パス 等は description で明示）

### 5.3 引数なし Tool

`"input": {}` でよい。LLM は空オブジェクト `{}` を渡す。

---

## 6. Output 規則

### 6.1 推奨構造（新規 Tool）

成功・失敗を LLM が機械的に扱えるよう、次を推奨:

```json
{
  "ok": true,
  "status": "ok",
  "result": {}
}
```

```json
{
  "ok": false,
  "status": "error",
  "error": "human_readable_code_or_message"
}
```

### 6.2 既存 Tool との互換

- **既存 Tool を一斉に上記形式へ変更しない。**
- 観測系（`get_gpu_status`, `get_cpu_status` 等）は `ok` / `status` / `error` を既に返す実装が多い。
- Legacy `cpu_status` は `{"status": "..."}` のみ — **例外 D**（後述）。

### 6.3 LLM への返却

Agent は `execute_tool` の戻り値を **raw JSON** で `role=tool` に載せる（stdout 要約は別経路）。  
構造化 error は LLM が受け取れる。

---

## 7. Error 規則

### 7.1 基本フロー

```text
Tool 実装
  ↓ 失敗（想定内）
構造化 dict（ok: false, error: ...）
  ↓
execute_tool がそのまま返却
  ↓
LLM（role=tool）
  ↓
Agent が次ターンを判断
```

### 7.2 Error オブジェクトに含めてよいもの

- `error` / `status` — 短い機械可読コードまたはメッセージ
- `recoverable` — 将来用（任意）
- `details` — 非秘密の補足

### 7.3 返してはいけないもの

- API キー、トークン、内部パス全文、スタックトレース（本番 Agent 経路）
- 想定外の例外は `execute_tool` が raise する場合あり — **例外 E**（後述）

### 7.4 例: read_url_text（SSRF）

```json
{
  "ok": false,
  "error": "ssrf_blocked:...",
  ...
}
```

P0 で確認した SSRF 対策を維持する。規約違反として削除・弱体化しない。

---

## 8. Side Effect（副作用）

### 8.1 分類（新規 Tool は Registry または description で明示）

| 値 | 意味 | 例 |
|----|------|-----|
| `read-only` | 状態を変更しない | `get_gpu_status`, `get_cpu_status` |
| `write` | ローカルファイル・Registry 等を変更 | `register_tool`, `apply_repair` |
| `external-effect` | ネットワーク・外部 API | `search_web`, `read_url_text` |
| `execute` | サブプロセス・コマンド実行 | `research_verifier` |

### 8.2 現状

既存 Registry には `side_effect` フィールドは **未一括導入**。  
代表 Tool は description / 実装から分類可能。新規 Tool から `side_effect` 推奨フィールドを追加してよい（任意）。

---

## 9. Security 規則

### 9.1 Registry の `risk`

| 値 | 意味 |
|----|------|
| `low` | 読取・合成が主 |
| `medium` | ネットワーク、Registry 書込、中程度の影響 |
| `high` | 任意コード実行等（現 Registry には未登録） |

### 9.2 セキュリティ観点の記述

Tool Contract として、該当するものを実装または description で明示:

- `network access` — HTTP GET/検索
- `filesystem access` — ファイル読書
- `process execution` — subprocess
- `external side effect` — 上記以外の外部影響

### 9.3 read_url_text（必須維持）

- HTTP/HTTPS のみ
- SSRF ブロック（loopback、link-local、file:// 等）
- サイズ・タイムアウト制限
- 詳細: `ai_tool/experimental/read_url/ssrf.py`

---

## 10. visibility

### 10.1 意味（現行コード準拠）

| 値 | Registry 存在 | LLM（Ollama tools） | execute_tool |
|----|---------------|---------------------|--------------|
| `agent` | はい | **公開** | 実行可（Gate 通過後） |
| 未指定 | はい | **非公開** | 実行可（内部・パイプラインから） |
| `pipeline` | 将来用 | 非公開 | パイプライン専用想定 |
| catalog `experimental_trial` | catalog 側 | trial のみ | 試験経路 |

**重要:** 「Registry にある」≠「Agent LLM から見える」。  
`create_ollama_tools` は `visibility == "agent"` のみフィルタする。

### 10.2 現状（2026-09-02）

- **agent 公開:** 9 Tool（`get_gpu_status`, `get_gpu_processes`, `cpu_status`, `get_cpu_status`, `get_system_time`, `get_memory_status`, `get_system_summary`, `search_web`, `read_url_text`）
- **非公開（visibility 未指定）:** Tool Builder 系 14 Tool 等

---

## 11. Registry 登録規則

新規 Tool 追加の正規フロー:

```text
1. 目的・Contract を定義
2. Input Schema を定義
3. Output / Error を定義
4. Security / Side Effect を確認
5. Python 実装（tools/... または ai_tool/...）
6. registry/tools.json へ登録
7. Tool Calling テスト（Schema 変換・実行・エラー返却）
8. integration test
9. registry/TOOLS_CHANGELOG.md に記録
```

**禁止:** 実装だけ作り Registry 未登録のまま Agent 向けに公開すること。

---

## 12. Tool 変更規則

変更時は CHANGELOG に **何を・なぜ** を記録する。

| 変更種別 | 互換性影響 |
|----------|------------|
| Tool ID 変更 | **破壊的** — 原則禁止。新 ID 追加 + 旧 ID deprecated |
| input schema 変更 | **高** — LLM プロンプト・既存セッションに影響 |
| description 変更 | **中** — Tool 選択挙動が変わる |
| output 変更 | **中〜高** — 下流の検証・LLM 解釈に影響 |
| behavior 変更 | **高** — 実測 evaluation の更新が必要 |
| security 変更 | **最高** — レビュー必須 |

---

## 13. CHANGELOG

**正本:** `registry/TOOLS_CHANGELOG.md`

大規模な変更管理システムは作らない。  
「いつ / 何を / なぜ」を人間が追える程度でよい。

---

## 14. EXCEPTIONS（例外）

すべての Tool が同一形式になるとは限らない。**例外を暗黙化しない。**

| 分類 | 例 | 扱い |
|------|-----|------|
| **legacy** | `cpu_status` — `status` 文字列のみ | 後継 `get_cpu_status` を優先。削除は別タスク |
| **experimental** | catalog 経由 trial Tool | `experimental_trial` visibility。本番 Registry と混同しない |
| **external integration** | Ollama / nvidia-smi / CIM | 取得不能時 unknown。固定値フォールバック禁止 |
| **special return format** | `get_gpu_processes` の `processes` 配列 | description で構造化 dict を明記 |
| **execute_tool raise** | 想定外 Exception | Tool 内で捕捉して構造化 error を返すのが望ましい。未対応は既知の例外 E |

新規例外を導入するときは CHANGELOG と本ドキュメント EXCEPTIONS に追記する。

---

## 15. 新規 Tool 追加手順（チェックリスト）

開発者向け手順:

1. [ ] 目的と他 Tool との境界を 1 文で書く
2. [ ] tool_id（snake_case）を決める。既存と重複しない
3. [ ] description（LLM 向け）を書く — 禁止パターンを避ける
4. [ ] `input` Schema（type + description + required）を定義
5. [ ] 戻り値: `ok` / `error` を検討
6. [ ] `side_effect` と `risk` を決める
7. [ ] 実装: `module` / `function`
8. [ ] `registry/tools.json` 登録。Agent 公開なら `visibility: agent`
9. [ ] `python -m pytest tests/test_tool_calling_rules.py` 
10. [ ] 必要なら `tests/ai_tool/agent_integration` を追加
11. [ ] `registry/TOOLS_CHANGELOG.md` 更新

---

## 16. 代表 Tool との整合（P1-2 確認）

| Tool | 分類 | メモ |
|------|------|------|
| `get_gpu_status` | 適合 | description・実測・ok/error あり |
| `get_cpu_status` | 適合 | Legacy との区別明記 |
| `get_gpu_processes` | 適合（D: output 形式は独自） | 構造化 dict。例外として明記済み |
| `read_url_text` | 適合 | Schema・SSRF・ok/error。P0 維持 |
| `create_tool_proposal` | B: visibility 未指定 | 意図的に LLM 非公開（パイプライン内部） |

---

## 17. 関連ファイル

| ファイル | 役割 |
|----------|------|
| `registry/tools.json` | Tool 登録正本 |
| `agent.py` | `create_ollama_tools`, `execute_tool` |
| `tools/system/tool_contract.py` | 規約検証・参照ヘルパ |
| `ai_tool/agent_integration/experimental_exposure.py` | Schema 変換（trial 共用） |
| `ai_tool/agent_integration/gpu_process_e2e.py` | `execute_registry_tool`（テスト用実行） |

---

## 18. 今回やらないこと（P1-2 スコープ外）

- Tool Registry 全面再設計
- 全 Tool の output 統一リファクタ
- file tools 本番公開
- Model Registry 変更
- LLM 自動 Tool 選択
- Agent 主経路の変更
