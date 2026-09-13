# Human Guide — 新規 Tool の作り方

「何を作ればいいか分からない」状態を減らすための手順書。  
用語は Diagnostic Framework Glossary（観測・実行・Gate 等）と矛盾しない。

**状態:** ADOPT CANDIDATE

## いつ Tool を作るか

1. Registry を検索し、既存 Tool で足りないか確認する
2. 複数 Tool の組み合わせで足りないか検討する
3. それでも不足する場合のみ新規 Tool を検討する（PROJECT_SPEC §3.2）

## 手順（7 ステップ）

### 1. Tool の目的を書く

1 文で書く。例:

> 「GPU の温度・使用率・VRAM を nvidia-smi から実測して返す」

### 2. Input を定義する

- パラメータは最小限にする
- 各パラメータに型・説明・必須/任意を付ける
- JSON Schema 形式で [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) に記載

引数なしの場合も明示: `input_schema: { "type": "object", "additionalProperties": false }`

### 3. Output を定義する

- 成功時のフィールド一覧または JSON Schema
- **失敗時の形**も必ず定義（`error_format`）
- 観測 Tool は `observation_source` 等の出所を含める（GPU Tool 参照）

### 4. 副作用を定義する

`side_effect` を選ぶ:

| 値 | 選ぶとき |
|----|----------|
| `read_only` | 状態を読むだけ（GPU/CPU 状態、検索） |
| `write` | ファイル作成・追記 |
| `modify` | 既存データの変更・削除 |
| `execute` | subprocess 等の実行 |
| `none` | 純粋計算 |

`read_only` 以外は人間承認を前提とする。

### 5. 禁止事項を書く

[TOOL_CONTRACT.md](./TOOL_CONTRACT.md) の `cannot` / `must_not` を書く。

例（観測 Tool）:

- 固定値へのフォールバック禁止
- ネットワーク送信禁止
- ファイル書き込み禁止

### 6. Test を書く

[TEST_CONTRACT.md](./TEST_CONTRACT.md) に沿ってテストケースを列挙する。

- 最低: Normal 1 件 + Safety 1 件
- 引数あり Tool: Invalid 1 件以上
- `tests/test_<name>.py` に pytest で実装（推奨）

既存 `test_tool()` だけに頼らない（引数なし・出力未検証のため）。

### 7. Catalog へ登録する

1. Tool Specification ファイルを保存
2. 実装・テスト完了後、人間レビュー
3. `registry/tools.json` へ追記（本番）
4. [CATALOG.md](./CATALOG.md) の Catalog Entry を作成（実験・採用状態を分離）

**自動登録はしない。**

## ディレクトリの置き方（新規のみ）

推奨:

```text
tools/<category>/<subcategory>/<tool_name>/
  tool.py
  README.md
  tests/test_<tool_name>.py
```

既存 Tool の配置は**変えない**。

## Registry 追記時のチェックリスト

- [ ] `name` が一意
- [ ] `module` / `function` が実装と一致
- [ ] `visibility` を意図的に選択（`agent` / `pipeline`）
- [ ] `risk` を設定
- [ ] `description` が LLM に渡しても誤解しない
- [ ] `input` が Specification の `input_schema` と一致

## よくある失敗

| 失敗 | 対策 |
|------|------|
| 戻り値が呼び出しごとにバラバラ | `output_schema` を先に書く |
| 失敗時に例外だけ | error dict を Specification に定義 |
| テストが引数なしのみ | TEST_CONTRACT の Invalid/Boundary を追加 |
| MCP を「安全」とみなす | `provider: mcp` は常に追加レビュー |

## 次に読むもの

- [CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md) — 全体フロー
- [examples/existing_get_gpu_status.md](./examples/existing_get_gpu_status.md) — 既存 Tool の Mapping 例
- [../README.md](../README.md) — AI-TOOL Layer（外部 Tool 実験）

## LLM 向け資料について

今回は **LLM 用 Tool Specification Context の常時投入は作らない**。必要時のみ Selector が subset を渡す設計を将来候補とする（Phase 12）。
