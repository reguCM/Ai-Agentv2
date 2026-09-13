# Help System H4 Core — Tool Selection / Resolution

**状態:** **完了承認**（人間、2026-09-08）。H4 Core ≠ H4 製品全体。merge / push / promote は別指示。  
**正本関係:** 本ファイルは層1（人間レビュー）。実装契約は [`docs/tech-specs/help-system-h4-selection-core.md`](../tech-specs/help-system-h4-selection-core.md)。根拠は [`docs/prds/help-system-h4-selection-core-decision-log.md`](help-system-h4-selection-core-decision-log.md)。  
**H4-1:** [`docs/prds/help-system-h4-stage-1.md`](help-system-h4-stage-1.md) はファイル読取の第一段階。H4-1 ⊂ H4 Core。H4 Core 完了 ≠ H4 製品完了。

---

## Human Review Summary

人間が短時間で承認判断するための要約。詳細・テスト・経路は層2/層3。

### 何を完了とするか

Chat の要求から **Capability Index 上の意味単位** を決め、Registry keywords で語彙を引き、Help で available を確認し、ちょうど1 Tool のときだけ `selected_tool` を付けて read-only bridge / Sandbox 注入の **判断** までを機械的にする。Tool 追加のたびに横断 allowlist を増やさない。

H4 製品全体（Help 英語検索、UI、`detect_tool_gap` 内部、Tool 一覧の LLM フィルタ、形態素解析）は完了条件に入れない。

### 採用した主要 Decision

| 決定 | 理由 |
|---|---|
| 意味の正本は Index、語彙は Registry keywords、対象 path は Index `look_first` | Tool 名ハードコードを正本にしない |
| web/gpu/cpu は Index に capability を足す（5件。CPU 二本は同一 capability） | keywords だけでは Help 正本に載せられない。legacy `cpu_status` は Tool 属性 |
| Classifier B: keyword 逆引き。共有だけなら `prefer_when_ambiguous`。複数 exclusive は全部残す | 固定意図表 `_RULES` を正本から外す |
| 正本 API は複数 capability。`selected_tool` は **1 Resolution あたり 0 または 1**。2+ candidate は `CANDIDATES_AVAILABLE` | `[0]` ranking を Core に入れない |
| 日本語一致は表層 substring（Latin は単語境界）。mutation には裸 verb も日本語 `ファイル` 単独も足さない。file付き表層 + intent×file対象 | プロファイル FP と正当日本語 mutation を両立する |
| 除外表は初期 `プロファイル` のみ。第2語彙にしない。write/execution の `look_first` は **消さない**（選択では無視） | 完全分割を Core で解かない。未観測の人間向け案内を壊さない |
| `read_file` の `next_action` は要求内 path 根拠があるときだけ。`look_first[0]` 黙読をやめる | 誤分類 read が `registry/tools.json` を自動実行するのを止める |
| Sandbox は Tool 名集合ではなく `dedicated_sandbox_required`。同一 Task に mutation Resolution が複数でも **各 selected_tool は1件** | 名 allowlist を残さない。単位の誤読を防ぐ |
| Help 確認は Index `tools[]` + `describe` / `local:`。`fallback="read_file"` しない | H4-1 の継続。英語フレーズ検索 0 件を Gap と即断しない |

### Known Issues / Residual Risks（残して採用）

問題が残っていても採用した理由は、**Core で日本語解析・Discovery 一致方向・LLM Tool 一覧まで解くと範囲が製品全体になる**ため。実害は分類 + `selected_tool` + Sandbox fail-closed + path 根拠 bridge で抑える。

- 表層 substring のため `プロファイル` 以外の未知衝突があり得る。除外表は解析器ではない。
- Registry keywords は Help / `search_tools` / `relevant_tools` に漏れる。英語 `edit`/`create`/`file` の過候補は現行どおり。
- path なし「ファイルを読んで」は bridge しない（Q25）。H4-1 の黙読テストは仕様変更で赤くなる。
- **list 誤分類:** `selected_tool=list_files` かつ path なし → `list_files(".")` が workspace root 一覧を自動実行し得る（Q30。Q25 と同種。今回は閉じない）。
- 「検索して」「使用率」だけの横断共有は確定しない（実装事故りやすい）。
- `cpu_observation` は候補2件のため **常に `selected_tool` なし**。
- file付き表層に無い正当 mutation は FN。audit「確認」は広い。
- LLM には全 agent Tool が渡る。概念 look_first 自動読取は残る。Help `_CAPABILITY_QUERIES` は残る。
- **空 `tools[]` の自然言語 Gap は到達不能（Deferred）。** Classifier B は Registry keywords → Index 逆引きのため、Index `tools[]` が空の capability（`test_execution` 等）は「pytestを実行する」からは required にならない。available 0 の Gap は **capability id が既に分かっているとき**（明示 resolve / expectation）にだけ立つ。`_RULES` を戻して NL Gap を復元しない。revisit: 空 tools 側に語彙を載せる別正本、または最小 agent Tool を Index に載せる設計。

### 特に人間が確認すべき高リスク項目

1. **Q25** — 黙読停止 vs path なし read の機械的成功が消える。テストを緑にするために `look_first[0]` を戻してはならない。  
2. **Q30** — list の `"."` 自動実行を Residual として受け入れるか（採用済み。変更するなら別fork）。  
3. **Q36** — 横断共有 keyword 規則。テスト不足で静かに誤る。  
4. **Q38** — CPU を ranking せず `CANDIDATES_AVAILABLE` のままにする。  
5. **除外表と file付き keywords** — 2件目を足したくなったら形態素へ。裸 `編集` を足すな。  
6. **write 側 `look_first` は残す** — 選択では無視。JSON から消さない。

### 完了承認

2026-09-08 人間承認。H4 Core の実装契約は充足したものとして閉じる。merge / push / production は対象外。下記「独立 ToDo」は Core を再開しない。次 Goal の設計 Packet・実装は未着手。

---

## Goals

要求 → Capability（Index）→ 候補 Tool（Registry + Help）→ ちょうど1件のときだけ実行判断（read-only bridge / Dedicated Sandbox 注入）までを、Tool 名の横断 allowlist なしでつなぐ。

完了の区別: 上記経路がコードで CONNECTED であり、下記 Requirements の回帰が同種再発を抑える。2026-09-08 人間が H4 Core を完了承認。pytest 件数や H4-1 完了、Help 検索の一般化をもって製品完了としない。

## Requirements

- [x] Index に `web_search` / `url_fetch` / `gpu_device_observation` / `gpu_process_observation` / `cpu_observation` を追加し、それぞれ `search_web` / `read_url_text` / `get_gpu_status` / `get_gpu_processes` / (`get_cpu_status` と `cpu_status`) を `tools[]` に載せる
- [x] Index `schema_version` を 2 にし、ルートに `classifier`（除外表・audit_intent・空 tools 実行系の audit 降格対象）を置く。`prefer_when_ambiguous` は該当 capability に置く
- [x] 空 `tools[]` capability の `suggested_minimal_tool` を Index に移す。実行選択に使わない
- [x] 正本分類は Classifier B（Registry keywords → Index 逆引き）。`_RULES` と H4-1 の `"file" in text` は正本から外す
- [x] Latin は単語境界、日本語は Registry 表層 substring。同一script埋没除外はしない
- [x] 共有 `ファイル`/`file` のみ → `prefer_when_ambiguous` が指す `workspace_file_read`
- [x] `registry_read` は keyword 逆引きで選ばない。read-only capability の `look_first` パスが要求に含まれるとき（および audit 降格）で足す
- [x] write/execution capability の `look_first` は Index に残し、選択 signal にも default bridge にも使わない
- [x] mutation Registry keywords: `edit_file` に file付き表層（`ファイルを編集` 等）。`create_file` に `ファイルを作` / `ファイル作成` / `新しいファイル`。裸の `編集`/`作成`/`作って`/`書き換え` と日本語 `ファイル` 単独は足さない。英語 `file` を `search_files`/`list_files` に足してよい
- [x] write-side は exclusive intent かつ file対象。除外語 `プロファイル` が `ファイル` 区間を含むヒットは write-side 根拠にしない（Help 等には適用しない）
- [x] 横断カテゴリの共有語だけ（単独の「検索」「使用率」）では capability を確定しない。file対象があるとき `検索` だけでは `web_search` を足さない
- [x] 明示 URI かつ競合 Tool の input に URL 欄 → `url_fetch`。汎用 web → `web_search`。汎用 GPU → device。GPUプロセス要求 → process。両側 exclusive（例: 温度とプロセス）→ 両方（Q4 / Q6）
- [x] `required_capabilities() -> list[str]` と `detect_required_tool_gaps() -> list` が正本。内部は単数 API を呼ばない。単数 compat は 0→None / 1→値 / 2+→明示エラー。削除しない
- [x] 1 Resolution = 1 capability。memory は `dict[task_id, list[CapabilityResolution]]`。snapshot `capability_resolution` は既存どおり flat list。同一 task+capability は upsert。required 再計算で落ちた分は resolution と `tool_gaps` を同じ reconcile
- [x] Help 確認済み available を `candidate_tools`。ちょうど1件のときだけ `selected_tool`。2+ は status `CANDIDATES_AVAILABLE`、`selected_tool` なし。Gap は available 0 のときだけ
- [x] `RESOLVED` ⇔ `selected_tool` がセット。`RESOLVING` は in-flight のみ。実行/bridge/mutation 判断は `selected_tool` があるときだけ
- [x] `read_file` の `next_action` は `selected_tool` かつ要求内 path 根拠（path/ファイル名形、または当該 capability の look_first パスが要求に含まれる）があるときだけ。`look_first[0]` デフォルトと `_VERIFIED_ROUTES` は正本から外す
- [x] `list_files` は list が `selected_tool` のとき bridge 可。path 無ければ `"."`（**Residual:** 誤分類時に root 一覧が自動実行され得る）
- [x] `search_files` は機械的 query が取れないなら `next_action` なし。`text[:80]` を query にしない
- [x] 同一 Task で `next_action` が2件以上なら **どれも inject しない**
- [x] pending inject は Tool 名集合ではなく、`selected_tool` かつ Registry `side_effect` が sandbox-write/write でないこと
- [x] search hit 後の次読取は `workspace_file_read` の Help 確認 Tool + 観測 hit path（名 `read_file` 固定を正本にしない）
- [x] Sandbox 起動は `selected_tool` の Registry `security.dedicated_sandbox_required`。同一 Task にそのような Resolution が2+でも各 `selected_tool` は1件。`required_mutation_tool()` はそのとき None（どれを正ともしない）が Sandbox は起動する
- [x] audit 意図かつ write/実行系なら write-side を落とす / `registry_read` へ。語は Index `classifier.audit_intent`
- [x] 下記「保持すべき回帰」をテストとして固定する
- [x] leftover（`_CAPABILITY_QUERIES`、`detect_tool_gap` 内部、単数 API、概念 look_first、Chat UI 等）を削除して完成としない

## Non-Goals

- H4 製品全体の完了宣言、Help 英語フレーズ検索の一般化、形態素解析
- 2+ Tool の legacy ranking（CPU を含む `get_cpu_status` 優先も Core ではしない）
- `detect_tool_gap()` 内部 matcher の変更、`create_ollama_tools` 最適化、任意 Help/ToolCatalog Registry
- Chat UI / events の `search_web` 表示、`CHAT_TRUST_BOOTSTRAP_ALLOWLIST`、`expected_tool` 複数形
- LLM に渡す Tool 一覧の capability フィルタ
- time/memory/summary の Index 化、単数 API 削除、英語 Discovery 過候補の是正
- 概念 Resolution の look_first 自動読取の廃止（別層）
- write/execution capability から Index `look_first` を削除すること
- list の path なし `"."` bridge を Q25 と同型に閉じること（Residual として残す）
- merge / push / production 反映
- **独立 ToDo 2件**（下記。Core 完了後の別 Packet。設計未着手）

## Constraints

- Capability 正本: `registry/workspace_concepts.json`。語彙正本: `registry/tools.json` `keywords`。実装: Registry `module`/`function`
- Help 確認: `prefer_tool_for_capability` に頼らず、Index `tools[]` + `describe` / `local:<name>`（H4-1 Discoveries: `"read file"` は 0 件、`describe("read_file")` は失敗しうる）
- `detect_tool_gap()` 内部は変更しない（H4-1 と同じ）。呼び出し側が capability id と Help 確認名を渡す
- Generation-Time Assumption Check: Registry/Index の値を別 allowlist へ複製しない。`{create_file, edit_file}` や `{read_file, search_files, list_files}` を正本に戻さない
- snapshot の `capability_resolution` は flat list のまま（`agent_test_runner.py` / `run_human_summary.py`）
- 概念 Index（`categories` / `concepts` の `look_first`）は定義案内の正本。capability の look_first と畳まない
- 実装前コードは `selected_tool = candidate_tools[0]` と look_first[0] 黙読をしていた。それは欠陥であり正本ではない（完了承認時点の正本は Classifier B + ちょうど1件のときだけ `selected_tool`）
- 除外表は `classifier.match_exclusions`。`tools[]` にも keywords にも載せない。初期は `プロファイル` のみ。2件目は再設計トリガ
- 作業 git: 明示指示なしに merge/push/promote しない

## Approach

1. Index / Registry データ（capability 追加、classifier、keywords、`prefer_when_ambiguous`、`suggested_minimal_tool`）。write 側 look_first は残す  
2. 要求 → `required_capabilities()` matcher（B + 除外 + write-side ゲート + 横断共有 + audit + look_first 選択は read-only のみ）  
3. capability ごと Help 確認 → candidate / selected_tool 一意 / Gap  
4. `next_action` path 根拠、複数 inject 禁止、side_effect で pending 可否  
5. Sandbox を `dedicated_sandbox_required` へ。複数 mutation Resolution 時の required 名は None  
6. 単数 API は wrapper。内部は複数形  
7. 回帰テスト（Xファイル、プロファイル、裸 verb、黙読禁止、2+ selected なし、CPU 二候補）

詳細なモジュール分割と順序は tech-spec。

## Open Questions

H4 Core についてなし（Residual は Known Issues。Core を再開しない）。

## 独立 ToDo（H4 Core 外。設計・実装未着手）

H4 Core 完了承認（2026-09-08）のあと、人間が立てた **独立 2 本**。Q4–Q6 を再開しない。次 Goal の設計 Packet はまだ作らない。

### 1. Task / Action Ownership

User Goal / Task Capability / Internal Action を分離する。

- `ファイルを編集する` のような要求は、ユーザー目的として **1つの edit Task**
- 内部処理として `read → understand/plan → write → verify` に分解してよい
- read と edit を独立したユーザー目的として並列化しない
- 原則として **1つの Sub-Agent が Task 全体を所有**
- 現行の複数 `CapabilityResolution`（同一 Task 上の list）を、Task 単位へどう畳むかを設計する
- H4 Classifier B / Q6 の capability 並列表記を「ユーザー Task」と同一視しない

### 2. Tool Gap → Tool Builder Bridge

Tool が無くても Goal から必要 Capability を認識し、Gap 後に作成側へつなぐ。

- 入口: 既存 Tool が無くても Task/Capability を認識する（**Tool 非依存**。`_RULES` 復活はしない）
- 既存 Tool で満たせるかを確認する
- 満たせない場合: 「この Tool を作れるか？」を評価する
- 既存 Tool の組合せで代替できるかも確認する
- Proposal / Builder への接続
- Human Gate をどこに置くかを決める
- 想定フロー: Goal → 必要 Task/Capability → 既存 Tool 確認 → Tool なし → Tool Gap → Tool 作成可能性評価 → 必要なら Proposal / Human Gate → Tool 作成
- 現行 H4 は Gap 確認後に Human Approval で **停止**する（`Toolは自動作成しません`）。この後続は本 ToDo

## Discoveries

- 2026-09-08 設計レビュー: capability `look_first` の in-repo 実行時消費者は `next_capability_action` の default read のみ。概念案内は `concepts`/`categories`。write 側削除は未観測の JSON 読者を壊し得るため不採用（残して無視）。
- 2026-09-08 H4-1（前提）: Help search `"read file"` は 0 件。`describe("local:read_file")` はヒット。

## Ambiguity Report

```
Ambiguity Report:
  Goals:        0.0   ✓ H4 Core の完了条件と製品全体の非完了が分離されている
  Acceptance:   0.25  ✓ 回帰ケースは列挙済み。Q36 の境界は tech-spec のテスト表に依存
  Boundaries:   0.0   ✓ Non-Goals / leftover / Residual を明示
  Alternatives: 0.0   ✓ 除外表・look_first 削除しない・[0] しない を採用/不採用済み
  Assumptions:  0.25  ✓ 対話ロック + 第一推奨を人間がレビュー済みとして扱う。out-of-tree consumer は NOT_OBSERVED
  ──────────────────────────────
  Aggregate:    0.10  ✓ below threshold (0.2 spec)
```

Caller: write-prd。指摘フェーズ完了済みのため grill 再面接はしない（仕様再オープン禁止）。Passive self-review。

## 保持すべき回帰（PRD 正本。tech-spec がテストへ落とす）

正当 mutation: ログファイルを編集して / テキストファイルを書き換えて / バックアップファイルを作って / ファイルを編集して / 新しいファイルを作って / 設定ファイルを書き換えて / 新規ファイルを作る。  
write-side にしない: ユーザープロファイルを編集 / プロファイル情報を更新 / 設定を編集して / 文章を作って / ファイルを確認して / 既存コードを修正する。  
path なし file-read → `next_action` なし。要求が `registry/tools.json` を含む read → その path の next_action 可。  
共有ファイル → prefer read。ファイル検索 → search、汎用 web 語なしなら web_search なし。明示 URI → url_fetch。汎用 GPU → device。GPUプロセス → process。両側 exclusive（温度とプロセス）→ 両方。CPU → candidate 2、selected_tool なし。available 2+ → CANDIDATES_AVAILABLE。available 0 かつ空 tools → Gap（suggested は実行されない）。Sandbox は dedicated フラグの selected_tool があるときだけ。単数 API は 2+ でエラー。Index tools[] は実在 Registry 名。  
既存: `test_safe_mutation_tools_p218.py` / sandbox P2-17 / H4-1 の fallback しない意図。
