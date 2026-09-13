# Help System H4 Core — Evidence / Decision Log

**状態:** **完了承認**（人間、2026-09-08）の根拠記録。H4 Core に新 Decision / 新 Q を足さない。  
**層1:** [`help-system-h4-selection-core.md`](help-system-h4-selection-core.md)  
**層2:** [`../tech-specs/help-system-h4-selection-core.md`](../tech-specs/help-system-h4-selection-core.md)  
**独立 ToDo（Core 外・未着手）:** 層1 PRD「独立 ToDo」2本。本ログで設計しない。

人間は通常読まない。実装が「なぜ」を疑ったとき、または再設計トリガで開く。

H4 Core の設計判断の追加はしない。対話ロック（Q1–Q24）と、第一推奨のち指摘修正（Q25–Q47、Q27 改訂、Q30 Residual、Q35 単位）を記録する。下記「コード調査結果」は **設計時** の in-repo 事実であり、完了承認後のコードの代替ではない。

---

## コード調査結果（現行。正本ではない）

調査時点の in-repo 事実。実装はこれを「正しい仕様」と読まない。

### Classifier / resolve

- `infer_required_capability` は `_RULES`（Python 正規表現の意図表）+ `_AUDIT` 降格。
- `resolve_capability` は **単数** capability。`candidate_tools` が非空なら **`selected_tool = candidate_tools[0]`**、`status=RESOLVED`。
- `_MINIMAL_TOOLS` はコード定数。空 tools の Gap 提案。
- `_VERIFIED_ROUTES` は Python (regex → path)。`read_file` の next_action に使う。
- `look_first[0]` は routes 非ヒット時の **default path**（要求にその path が無くても `registry/tools.json` を読む）。

### Orchestrator / agent_turn

- `capability_resolutions: dict[task_id, CapabilityResolution]`（Task あたり1件で上書き）。
- `snapshot()["capability_resolution"]` は **flat list** of `as_dict()`。
- `required_capability()` は H4-1: ファイル系だけ `workspace_file_read`。web/gpu/cpu は **Tool 名**。
- `pending_capability_action` は名集合 `{read_file, search_files, list_files}`。
- `required_mutation_tool` は名集合 `{create_file, edit_file}` かつその1 Resolution が RESOLVED。
- `agent_turn` は LLM に **全 agent-visible Tool** を渡す。mutation は Sandbox 未起動なら `sandbox_session_required`。
- search hit 後 `_pending_observation_action` は **ハードコード `read_file`**。

### Help / Discovery

- `LocalToolProvider.capabilities` = Registry `keywords`。
- Help `_match_query`: **query ⊆ metadata**（短い `/h 編集` が長い keyword に当たる）。
- `search_tools`: **keyword ⊆ request**。
- `relevant_tools`: keyword ⊆ request（監査。LLM 一覧は絞らない）。
- `is_agent_task`: keywords かつ `observation_source==real`。create/edit に `observation_source` は **無い**。
- `prefer_tool_for_capability`: leftover `_CAPABILITY_QUERIES`（`read file` は 0 件）。H4-1 は Index tools + `describe`/`local:`。

### Index

- ほぼ全 capability の `look_first` が `["registry/tools.json"]`（write/execution も含むコピー）。
- 概念案内は `categories` / `concepts` の look_first。**capability 欄は読まない。**

### Mutation keywords 現行

- `create_file`: `sandbox`, `file`, `create`, `新規作成`
- `edit_file`: `sandbox`, `file`, `edit`, `exact replacement`
- 日本語 `ファイル` は read/list 側。search_files には `ファイル` も `file` も無い。

---

## look_first consumer 一覧

| 消費者 | 入力 | write/execution capability の look_first |
|---|---|---|
| `load_workspace_index` | capabilities **含む** 全 group | 欄があればパス実在チェック。欄必須ではない |
| `detect_unknown_concept` | **concepts / categories のみ** | 使わない |
| `run_human_summary` next_actions | concept_resolution 結果 | 使わない |
| `next_capability_action` | 当該 capability spec | **唯一の実行時消費者**（default read）。Q25 でこの用途を正本から外す |
| `test_index_contains_only_existing_files` | categories, concepts のみ | 見ない |
| `docs/` | — | look_first 記述 **NOT_OBSERVED** |

**Q27:** 選択のためデータ削除は不要。未観測の JSON 人間読者を壊す可能性が NOT_OBSERVED のため **残して Classifier が無視**。

概念 look_first の自動読取は **別層**（Q46）。capability Q25 と同一視しない。

---

## Decision 全表

### 対話ロック

| ID | 決定 | 代替（不採用） | 不採用理由 |
|---|---|---|---|
| Q1 | 範囲は選択/Gap/expectation/read-only bridge/Sandbox 判断 | 製品全体 | leftover が消える |
| Q2 | web/gpu/cpu を Index に足す | keywords のみ / ID を足さない | Help 正本に載せられない |
| Q3 | 5 semantic capability。CPU 二本は同一 capability | Tool 名クローン、CPU を2 capability | 意味単位と legacy Tool 属性を混ぜない |
| Q4 | 意図: CPU / URL / 汎用web / GPUプロセス / 汎用GPU | 親 capability、汎用GPUで両方必須 | 過剰結合 |
| Q5–6 | B: 逆引き、共有は prefer、複数 exclusive は全部 | IDF、文字長、「具体語」リスト | 第2語彙化 |
| Q7 | 複数形正本。単数は 0/1/2+エラー。削除しない | 常に first、即削除 | 折りたたみ禁止。out-of-tree NOT_OBSERVED |
| Q8 | B は file 含む全 Index | file だけ `"file" in text` | 二重分類器 |
| Q9 | 汎用 file→prefer read。registry_read は look_first 等 | 両 capability を keyword でマージ | 同じ read_file でも意味が違う |
| Q10 | `_RULES` を正本から外す | Python 意図表を残す | allowlist 再発 |
| Q11–13 | 1 res=1 cap。snapshot flat。memory list。upsert+reconcile | 複合キー、ネスト snapshot | 既存 consumer が flat list |
| Q14–15 | selected はちょうど1。2+=CANDIDATES_AVAILABLE | `[0]` ranking | ranking は H4+ |
| Q16 | suggested は Index、実行に使わない | `_MINIMAL_TOOLS` で呼ぶ | Gap と実行の混同 |
| Q20-A | Latin 境界、日本語 substring | 形態素必須、同一script除外を全面適用 | ログファイル FN / Core 範囲 |
| Q23修 | 裸 verb と mutation の日本語 `ファイル` を足さない。file付き表層+組合せ | 裸 `編集`、mutation に `ファイル` | Discovery 漏れと object 単独 mutation |
| Q24=1 | 除外初期 `プロファイル` のみ | 形態素 Core、FP 受け入れ、同一script除外 | 正当 Xファイルを落とす / 解析を Core に入れる |

### 第一推奨のち指摘で確定

| ID | 決定 | 代替（不採用） | 不採用理由 |
|---|---|---|---|
| Q25 | read next_action は path 根拠のみ。look_first[0] 黙読廃止 | 黙読維持 | 誤分類 read の自動実行 |
| Q26 | look_first 選択 signal は read-only と registry_read のみ | 全 capability の look_first で選択 | write 側コピーが mutation を指名する |
| Q27 | **look_first を write 側から削除しない**（無視） | 削除して誤用防止 | 人間向け JSON 案内は NOT_OBSERVED。削除は canonical 破壊リスク |
| Q28 | `_VERIFIED_ROUTES` を capability 正本から外す | Python 表を残す | Index との二重定義。概念層は残す |
| Q29 | search `text[:80]` 禁止。query 機械抽出できなければ next_action なし | 長文を query にする | 無関係全文検索 |
| Q30 | list は selected 時 `"."` 可。**Residual として明記** | Q25 同型で path 必須 | Tool 省略時意味が "."。閉じるなら別fork |
| Q31 | next_action 2+ なら inject なし | `[0]` inject | read+edit 同時黙読 |
| Q32 | pending は side_effect と selected_tool | 名集合3件 | allowlist 再発 |
| Q33 | search-hit 次読取は Help 確認した workspace_file_read Tool | 名 read_file 固定 | H4-1 と同じ正本 |
| Q34 | Sandbox は `dedicated_sandbox_required` | 名集合 | 同上 |
| Q35 | Task 上 mutation Resolution 2+ なら Sandbox 起動、required 名 None。**各 Resolution の selected は高々1** | 1 Resolution に複数 selected | 契約違反。誤読防止を明文化 |
| Q36 | 横断共有だけ（検索、使用率）では確定しない。file対象時 検索だけで web を足さない | 片方へ prefer | 誤家族確定 |
| Q37 | audit 降格を Index classifier へ | `_RULES` に残す / 廃止 | 監査で mutation しない現行を残す |
| Q38 | cpu_observation は常時 CANDIDATES_AVAILABLE | Core で get_cpu_status を選ぶ | Q14 ranking 禁止 |
| Q39 | time/memory/summary を Index に足さない | 全部載せる | 範囲膨張 |
| Q40 | 日本語一致は A のまま。除外を file 以外に広げない | GPU にも除外表 | 第2語彙 |
| Q41 | file付き表層の最小集合（`ファイルを作` 等） | 裸 verb | Discovery |
| Q42 | 除外正本は Index `classifier`。schema 2 | 隠れた Python set | 適用点が不明になる |
| Q43 | prefer は read / gpu device / web_search | CPU 間 prefer | ranking |
| Q44 | URL は URI 形 + schema URL 欄 | URL Tool 名表 | allowlist |
| Q45 | search/list に英語 `file` | search に日本語 `ファイル` 必須、mutation に `ファイル` | 方針矛盾 |
| Q46 | 概念 look_first は変えない | 一緒に黙読停止 | 別層 |
| Q47 | leftover を削除しない | 掃除して完成 | 偽完了 |

---

## NOT_OBSERVED / NOT_DETERMINED

| 項目 | 判定 | 含意 |
|---|---|---|
| 単数 API の worktree 外 caller | NOT_OBSERVED | 削除しない |
| write/execution `look_first` を人間が読む用途 | NOT_OBSERVED | **削除しない**（Q27） |
| `プロファイル` 以外の高頻度 `*ファイル` 非file語 | NOT_DETERMINED | 除外を増やさない。未知衝突は Residual |
| 概念 look_first と capability look_first を同一視した製品意図 | NOT_DETERMINED | 畳まない |
| list `"."` 自動実行の実運用実害 | NOT_OBSERVED | Residual。Core 中に Q25 同型へ黙って変えない |
| Help 過候補が Sandbox なしで mutation 成功するか | 現行は fail closed を**観測**。将来フラグ欠損は revisit | 分類では閉じないと明記 |

推測で「用途は無いから消してよい」としない。

---

## 詳細経路

### 正当 mutation（例: ログファイルを編集して）

1. substring `ファイルを編集` → edit exclusive。除外語に非該当（`ログファイル` ≠ `プロファイル`）。
2. file対象あり → `workspace_file_edit`。
3. 共有 `ファイル` もあるが、exclusive が既にあるので `prefer_when_ambiguous` は使わない（Q5: prefer は共有だけのとき）。read は残さない。
4. edit が unique `edit_file` → その Resolution は RESOLVED。
5. Sandbox は edit のフラグで起動。

### プロファイルを編集

1. 表層は `ファイルを編集` を含む。
2. 除外表が file付きヒットを write-side 根拠から落とす。
3. read 側 A の `ファイル` FP は残してよい。
4. mutation selected なし → Sandbox 不起動。LLM が edit しても fail closed。

### 誤分類 read（path なし）

1. `workspace_file_read` unique → selected `read_file` にはなり得る。
2. Q25: next_action なし。現行 look_first[0] は廃止。
3. LLM 自発 read は Path Guard へ。

### 誤分類 list（Residual）

1. unique `list_files` → next_action `path="."` があり得る。
2. Q25 と同種の自動実行。Q30 で残す。分類回帰で list 誤確定を減らす。

### CPU

1. `cpu_observation` → candidate 2 → selected なし → bridge なし。
2. LLM が Tool を呼ぶ。

---

## Gate / Layer（実害）

| 害 | 抑える層 | 抑えない層 |
|---|---|---|
| プロファイル→mutation 分類 | matcher + 除外表 | Help / relevant_tools / LLM 一覧 |
| 裸 verb→mutation 分類 | keywords 限定 | 英語 edit/create |
| ファイル単独→mutation | prefer read | read 誤分類 |
| read 黙読 tools.json | Q25 | LLM 自発 read |
| list root 一覧自動 | 分類（唯一件にしない） | **Q30 採用後の list 唯一件** |
| mutation 実行 | selected + dedicated フラグ / fail closed | LLM が呼ぶこと |
| ranking 誤選択 | 2+ で selected なし | LLM が一方を呼ぶ |
| Tool Gap 捏造 | available 0 のみ Gap | 提案文面 |
| workspace 外 / Production | Path Guard / Sandbox / production_write | 分類器 |

---

## 保持すべき回帰 / Deferred / revisit

PRD と tech-spec に同一リストがある。ここでの複製は変換漏れ防止用。

**回帰:** ログ/テキスト/バックアップファイル mutation、ファイルを編集して、新しいファイルを作って、設定ファイルを書き換えて、新規ファイルを作る、プロファイル系と裸 verb とファイル確認と既存コード修正は write-side にしない、path なし read の next_action なし、registry/tools.json 言及 read は可、prefer read、ファイル検索で web を足さない、URI→url_fetch、GPU 分岐、CPU 二候補、2+ CANDIDATES_AVAILABLE、空 tools Gap で suggested 非実行、Sandbox フラグ、単数 API 2+ エラー、Index tools 実在、P218/P217、H4-1 fallback しない。

**Deferred:** 形態素、Help クエリ一般化、ranking、detect_tool_gap 内部、create_ollama_tools、Help Registry、UI search_web、trust bootstrap、expected_tool 複数形、LLM フィルタ、time/memory/summary、単数削除、英語 Discovery、概念 look_first 廃止、write look_first 削除、list "." を Q25 同型化、merge/push。**空 `tools[]` の自然言語 Gap discovery**（`test_execution` ←「pytestを実行する」）。Classifier B は Registry 語彙に載る Tool しか逆引きできない。Gap は capability 既知かつ available 0 のときだけ。`_RULES` 復元は不採用のまま。

**意図（欠陥ではない）:** file付き mutation は exclusive で write-side だけを残す。共有 `ファイル` による prefer read は、共有 keyword **だけ**のとき（Q5 / Q9）。GPU process 要求は process exclusive のみ。device+process は両側 exclusive のときだけ（Q4 / Q6）。

**revisit:** tech-spec `revisit_trigger` と同一。

---

## 変換チェック（層1/2 への損失防止）

| 項目 | 層1 PRD | 層2 tech-spec | 本ログ |
|---|---|---|---|
| 主要 Decision | Human Review 表 + Requirements | 採用仕様 + Index/keywords 契約 | Decision 全表 |
| Known Issues / Residual（list "." 含む） | Human Review + Non-Goals | F11 + Deferred + revisit 11 | 経路 + Gate |
| Q27 削除しない | Constraints / Non-Goals | 不変条件 11 | consumer 一覧 |
| Q35 単位 | Human Review / Requirements | 不変条件 1, 15 / F10 | Q35 行 |
| 回帰 Test | 末尾リスト | Regression + F 表 | 回帰節 |
| Deferred | Non-Goals | Deferred 節 | Deferred 節 |
| do_not_assume | Constraints / Discoveries | do_not_assume | NOT_OBSERVED |
| 高リスク Q25/Q30/Q36/Q38 | Human Review 確認項目 | Sequence / F 表 | 第一推奨表 |
| 独立 ToDo 2本 | 独立 ToDo 節（Core 外） | Open Questions から層1へ参照 | 状態行から層1へ参照。新 Q にしない |

欠落があれば本ログを正として PRD/tech-spec を直す。実装で本ログだけを「新仕様」にしない。H4 Core 完了後の独立 ToDo は層1が置き場。
