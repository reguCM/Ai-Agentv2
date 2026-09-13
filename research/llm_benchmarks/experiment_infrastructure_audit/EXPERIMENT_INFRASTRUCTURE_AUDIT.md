# 実験基盤・問題解決ループ 実装監査

**監査種別:** 読み取り専用。実験実行・Test実行・コード変更・モデル変更はしていない。  
**監査日:** 2026-09-01  
**結論の採用対象ではないもの:** Qwen / Gemma / DeepSeek / GPT / Cursor 採用、Schema、正式 Mapping、Controller、Native Tool Calling 採否、本番接続。

本報告書はコードと既存一次資料から確認できた事実だけを書く。想定構造は書かない。存在しない経路を CONNECTED としない。

判定の区別:

| 表現 | 意味 |
| --- | --- |
| 実装されていない | 該当関数・呼び出しがコード上に無い |
| 実装されているが不十分 | 関数はあるが、要求する区別・安全性・追跡が足りない |
| 実装されているが今回確認できない | コードはあるが本監査では実行していない |
| コード上成立している | 生成 → 引数 → 保存/実行 → 次工程までソースから追えた |
| 実際に動作確認済み | 既存実験結果ファイルに、その経路の実行記録がある。本監査では再実行していない |

---

## 最終問いへの答え（先に）

### 1. 土台として技術的にまともか

**現時点の実験群は、単一の問題解決システムではない。** 同趣旨のループが複数ディレクトリに複製されており、互いに import していない。本番 `agent.py` / Registry / Dispatcher へも接続していない。

個別に見ると:

- 隔離 workspace 上の `read_file` / `list_files` / `search_files` / `apply_patch` / `run_test` / `run_program` は、判断層・判断ループ最小・再判断・実コード実験のそれぞれで **コード上成立している**。
- LLM → 判断抽出 → Mapping → 1 Tool → 結果返却、という段階のうち、**判断抽出層は未実装**。Mapping は正規表現の仮実装であり、LLM の「次手」と実行 Tool がずれる経路がコード上存在する。
- したがって「実コードと実エラーを入力し、判断を受け取り、調査・修正・Test・再判断するシステムの土台」としては、**Tool 実行と Test 返却の部品はあるが、判断を Tool へ落とす接続が信頼できない。**

総合評価は後述 **D（構造的問題あり）**。部品単体は B〜C。

### 2. いま LLM 能力を測ると歪むか

**歪む可能性は高い（判断層・判断ループ最小）。**  
根拠は推測ではなく、既存一次資料と Mapping ソースの一致である。

Gemma `judgment_loop_min` Turn 1（`results/20260901T024054Z/gemma3_12b/run.json`）:

- LLM 本文は `main.py` / `helper.py` / `tests/test_main.py` の全文を要求している。
- Mapping 候補ではそれらが `M2`（`execute: false`）。
- 本文末尾の `Run Tests Again` が唯一の `M1` になり、実行 Tool は `run_test`。
- ログの `judgment_interpretation.next_action` は `"run_test"` であり、LLM の第一要求ではない。

このずれを「Gemma がテスト再実行を次手とした」と読むと、モデル評価が歪む。

---

## A. 監査範囲

### 読んだコード（主）

| 領域 | パス |
| --- | --- |
| 判断ループ最小 | `judgment_loop_min_experiment/{bench,mapping,workspace,execute}.py` |
| 判断層 | `judgment_layer_experiment/{bench,mapping,observe,workspace,execute}.py` |
| 問題解決（初期） | `problem_solving_experiment/{harness,dispatch,catalog,adapters}.py` |
| 再判断 | `problem_solving_experiment/{rejudgment_bench,rejudgment_workspace,rejudgment_execute}.py` |
| 実コード | `problem_solving_experiment/{real_code_bench,real_code_workspace}.py` |
| 調査連鎖 | `problem_solving_experiment/{problem_solving_success_case_*,chain_conditions_*}.py` |
| Problem Analysis | `problem_analysis_bench.py`（他 PA ベンチは入口のみ） |
| Tool Calling 圧縮 | `tool_calling_compression_experiment/{bench,workspace}.py` |
| 上位判断 | `upper_judgment_experiment/{capture.py,UPPER_JUDGMENT_EXPERIMENT.md}` |
| 本番 Agent | `agent.py` 冒頭（実験からの import 無しを確認） |
| 本番 workspace Tool | `tools/file/workspace/_paths.py` |
| LLM クライアント | `tools/system/llm.py` の `chat()` |

### 読んだ既存結果（再実行していない）

- `judgment_loop_min_experiment/results/20260901T024054Z/gemma3_12b/run.json`
- `JUDGMENT_LOOP_MIN_EXPERIMENT.md`
- `JUDGMENT_LAYER_EXPERIMENT.md`
- `PROBLEM_SOLVING_REJUDGMENT_EXPERIMENT.md`
- `UPPER_JUDGMENT_EXPERIMENT.md`

### 存在するが本監査で実行していないコード

`research/llm_benchmarks/mapping_harness_validation/` に、判断ループ最小の Mapping を SUT として呼ぶ検証コードがある。結果ディレクトリは無い。本監査では実行していない。**検証済みとはしない。**

### 読まなかったもの

- `research/llm_benchmarks/` 直下の古い FA / repair / environment ベンチ一式（Tool 作成パイプライン。今回の実コードデバッグループとは別系統）
- `capability_route_dataset/` 配下の Web 検索診断実験
- 本番 Registry の全 Tool 実装

これらを「問題解決ループの一部」とはしない。

---

## B. 現在の実装構造

コードから確認できる実構造。矢印は import / 呼び出し。

### 系統は複数あり、合流していない

```text
[本番]
agent.py
  → tools.system.llm.chat
  → 本番 Ollama tools / Registry 経路（本監査では詳細未追跡）
  ✗ research.llm_benchmarks.* からの import は無い

[共通クライアントのみ共有]
各実験 bench
  → tools.system.llm.chat / get_llm_profile / stop_model
  → 本番モデル設定を読む
  ✗ 本番 Registry / execute_tool には接続しない（各 workspace コメントと dispatch 実装）
```

### 系統 1: 自然言語 → 仮 Mapping → 実験専用 Tool（判断層 / 判断ループ最小）

```text
bench.run_one()
  → chat(model, messages)          # tools= は渡さない
  → classify_mapping(raw, known_files)
  → workspace.dispatch(name, args)
       → read_file / list_files / search_files / apply_patch
       → execute.run_test / run_program
  → messages に Tool 結果を user として追加
  → 次 Turn の chat
```

`judgment_layer_experiment` と `judgment_loop_min_experiment` は **同型のコピー**。`classify_mapping` は別ファイルで、選択規則が異なる（E / F 参照）。互いに import しない。

### 系統 2: Native / テキスト JSON Tool Calling（再判断 / 実コード / 圧縮）

```text
rejudgment_bench.run_one() / real_code_bench
  → chat(..., tools=OLLAMA_TOOLS) またはテキスト JSON 解析
  → workspace.dispatch
  → apply_patch 成功時はハーネスが pytest + main.py を追加実行
  → messages に結果
```

Mapping モジュールは使わない。LLM が Tool 名を出す前提。

### 系統 3: 実験 catalog + JSON action（初期 problem_solving harness）

```text
harness._run_turns()
  → chat（catalog を System に埋め込み）
  → _parse_action(text)  # {"action":"tool","name":...,"arguments":{}}
  → dispatch(name) → adapters.* 
       ファイル Tool は tools.file.workspace（リポジトリ root）
  → experiment_test_source は一時ファイル
```

対象は fixture の `main.py` 連鎖ではなく、**本番 `tools/system/cpu/cpu_status.py` を一時上書きして test_tool する**（H / N 参照）。

### 系統 4: 調査連鎖 Mapping（success_case / chain_conditions）

```text
success_case_bench
  → chat（Tool 名を Prompt に出さない）
  → map_information_requests / next_mapping
  → adapters.EXISTING_FILE_TOOLS  # リポジトリ workspace の read/list/search
```

修正・pytest ループは **この系統には無い**（読取連鎖の観測）。

### 系統 5: Problem Analysis

```text
problem_analysis_*.py
  → chat
  → 出力を保存
  ✗ Tool / Mapping / Test 再実行は無い（problem_analysis_bench.py 先頭コメント）
```

### 系統 6: 上位判断（Cursor / GPT）

```text
upper_judgment_experiment.capture
  → 実 pytest / main.py を保存
  → GPT: PROMPT.txt を書くのみ（ライブ呼び出し NOT_CONNECTED）
  → Cursor: 別 Solver セッション。実験コードの Mapping/Tool ループではない
```

### 存在しない単一パイプライン

```text
agent.py → judgment → mapping → tool → filesystem / test
```

この一連は **コード上 CONNECTED ではない。**

---

## C. 実際のデータフロー

以下は **判断ループ最小**（現時点で「判断→Mapping→Tool→返却」が一つの関数に揃っている系統）を段階ごとに記録する。他系統は差分だけ書く。

対象: `judgment_loop_min_experiment/bench.py` `run_one()`。

| 段階 | 状態 | ファイル / 関数 | データ |
| --- | --- | --- | --- |
| 入力 | コード上成立 | `execute.build_initial_user` | pytest / `python main.py` の command, exit_code, stdout, stderr |
| LLM | コード上成立 | `tools.system.llm.chat` | `messages: list[dict]`。`tools` 引数は渡さない |
| LLM出力 | コード上成立 | `response.message.content` | `raw` 文字列。thinking があれば別保存 |
| 判断抽出 | **未実装** | なし | `mapping_input = raw`（全文）。`observe.extract_judgment_fields`（判断層）も本文コピー |
| Mapping | コード上成立（仮） | `mapping.classify_mapping(text, known_files)` | `candidates`, `execute`（1件 or None） |
| Tool選択 | コード上成立 | `bench`: `execute = mapping["execute"]` | 実行可能候補から 1 件 |
| Tool引数 | コード上成立 | `execute["tool_arguments"]` | 例: `{"path": "helper.py"}` / `{}` |
| Tool実行 | コード上成立 | `workspace.dispatch` | HANDLERS または `unknown_tool:{name}` |
| Tool結果 | コード上成立 | `dump_result` + `sent_for_tool` | JSON 最大 3500 文字に切り詰めあり |
| LLMへの再入力 | コード上成立 | `messages.append({"role":"user", ...})` | 読取成功時は `format_file_result`。`run_test` 経由は `format_execution_block`。**パッチ後だけ** `format_test_failure` |
| 再判断 | コード上成立 | 次 Turn の `chat` | 会話履歴全体。独立した state オブジェクトは無い |

**判断層との差分:** `format_investigation_result` で返す。`run_test` 成功時に `python main.py` を追加実行して `test_result` に入れるが、その program 結果を LLM へ返すかは `format_investigation_result` が JSON dump するかどうかによる（run_test の payload 自体は pytest のみ）。

**再判断系統との差分:** Mapping 無し。native `tool_calls` を複数件/Turn 実行できる。パッチ後は必ず `test_feedback_user`。

**PA:** LLM 出力で停止。以降の段階は未実装。

---

## D. 判断層

「判断層」という独立モジュールは無い。あるのは:

1. Prompt（自然言語で次を述べさせる）
2. 生出力の保存
3. 仮 Mapping

確認項目:

| 項目 | 判定 | 根拠 |
| --- | --- | --- |
| 判断を構造化しているか | 未実装 | `current_problem` 等は `"NOT_EXTRACTED"`（`bench.py` judgment_interpretation） |
| 自然言語を Keyword 検索していないか | **している** | `mapping.py` の INSPECT / TEST_HINT 等 |
| 複数判断の扱い | 1 Turn 1 実行 | `_prefer` または `executable[0]` |
| 今すぐ vs 将来 | 区別しない | 「After that I may need to run tests」と「inspect helper.py」を同一 `text` で走査 |
| ファイル名抽出 | known_files の部分文字列 | workspace 上の実ファイル名に依存。未知パスは取れない |
| Tool名抽出 | LLM からは取らない（系統1） | Mapping が Tool 名を付ける |
| Tool引数 | Mapping が作る | 読取は path のみ |
| 曖昧判断 | mapping_gap / M4 | 実行せず idle 停止あり |
| 判断不能時 | idle_no_mapping（2 Turn 連続で execute 無し） | `bench.py` |
| Mapping失敗の検知 | 部分 | `mapping_gap` と `M2` は記録される。ただし実行された M1 があると、M2 のファイル要求は「失敗」として止まらない |

「helper.py を読む必要がある」→ `read_file(helper.py)` にできるか:

- **近いフレーズ**（ファイル名の前後 64 文字に inspect/read 等）なら M1 になり、コード上は `read_file` になる（`_near_inspect`）。
- **離れた全文要求**（Gemma 実ログ）では M2 になり実行されない。

これは Mapping の性質であり、判断層の構造化ではない。

---

## E. Extraction

**独立した抽出層は実装されていない。**

| 実験 | 抽出の実態 |
| --- | --- |
| judgment_loop_min | `mapping_input = raw`。候補は Mapping 内部の正規表現ヒット |
| judgment_layer | `extract_judgment_fields`: `llm_decision = 本文全部`。`requested_information = "NOT_EXTRACTED"`。`requested_target` は Mapping 候補の target 列 |
| rejudgment / real_code | native tool_calls または JSON / named fence。自然言語判断の抽出は無い |
| success_case | `extract_py_mentions` + 近傍リクエスト語。これは Mapping 寄りの抽出 |
| PA | 出力全文を保存。機械抽出無し |

ログ上 `selected_judgment` に相当する欄は、判断ループ最小では `mapping_output`（実行された候補）である。LLM が先に述べた行動ではない。

---

## F. Mapping

実装は複数あり、**正式仕様ではない**（各ファイル先頭コメント）。

### F.1 judgment_loop_min `classify_mapping`

処理順:

1. known_files に含まれるファイル名言及 → inspect 近傍なら M1 `read_file`、否则 M2（実行しない）
2. LIST / TEST / PROGRAM ヒント → それぞれ M1
3. コードフェンス → 条件付きで `apply_patch`
4. 実行可能候補を `_prefer`: `read, list, search, run_test, run_program, write` の順で 1 件

`_near_inspect`: ファイル名マッチ位置の前後 **64 文字** に INSPECT 正規表現。

`TEST_HINT`: `run (the )?tests?` 等。本文中のどこか一箇所で足りる。

**helper.py を読む vs run_test:**

問題:

LLM がファイル全文を要求しても、inspect 語がファイル名から 64 文字超なら read は M2。同じ本文に `Run Tests Again` があれば TEST_HINT が M1。`_prefer` は実行可能だけを見るため **run_test が選ばれる。**

根拠: `mapping.py` `_near_inspect` / `TEST_HINT` / `_prefer`、および既存結果 `gemma3_12b/run.json` の `mapping_candidates`。

確実性: コード上確認済み。当該 run は実際に動作確認済み（既存結果）。

影響: LLM 評価を Mapping 失敗と混同する。

推奨: 追加の LLM 実験の前に、固定判断文で Mapping だけを検証する（本監査では実行していない）。

### F.2 judgment_layer `classify_mapping`

- フェンスを **先に** M1 `apply_patch` として積む
- 次に TEST / PROGRAM / LIST
- その後ファイル言及。読取意図は前後 **48 文字**（`_file_has_read_intent`）
- 実行は `executable[0]`（リスト先頭）。`_prefer` は無い

そのため「helper を読め」と「テストを走れ」が両方 M1 なら、**TEST_HINT の方が先に配列され、run_test が実行される。**  
既存 `JUDGMENT_LAYER_EXPERIMENT.md` の DeepSeek 記述と一致する。本監査ではその run.json を全行再読していないが、選択規則はコード上確認済み。

### F.3 複数ファイル

```text
「helper.py と main.py を確認する」
```

- 両方 known かつ両方近傍に inspect があれば、候補は 2 件の M1 `read_file` になる。
- **実行は 1 件/Turn。** もう一方は同じ Turn では実行されない。
- 次 Turn で LLM が再要求する構造にはなっている（会話に結果が残るため）。

同時 `read_file(helper.py)` と `read_file(main.py)` を 1 Turn で回すコードは、系統 1 には無い。系統 2（native 複数 tool_calls）にはある。

### F.4 失敗時の追跡

候補配列は `mapping_candidates` として run.json に残る。  
「なぜこの Tool か」は `reason`（例 `run_test`, `inspect_named_file`）まで。  
「本文のどの文を次手としたか」の span / 採用理由の自然言語は **保存しない。**

---

## G. Tool

系統 1/2 の実験専用 Tool（`judgment_loop_min_experiment/workspace.py` を代表。判断層・再判断も同型）。

本番 Registry の同名 Tool とは **別実装**。

### list_files

- 入力: `path`, `recursive`, `glob`
- 処理: workspace 配下を列挙。`.git` / `__pycache__` 除外
- 出力: `{ok, path, entries: [{path, kind}]}`
- パス: `resolve_in_workspace`。`..` と root 外を拒否
- 作業ディレクトリ: 引数の fixture コピー先

コード上成立。本監査では未実行。

### search_files

- 入力: `query` 必須、`path`, `glob`
- 処理: **部分文字列**。正規表現ではない
- 空 query は `{ok: false}`
- 読取失敗行は `continue`（黙ってスキップ）

コード上成立。本監査では未実行。

### read_file

- 入力: `path`, 任意 `offset`/`limit`（1-based）
- 欠ファイル: `{ok: false, error: "ファイルが存在しません"}`
- 出力: `{ok, path, text, total_lines}`

コード上成立。既存 Gemma 経路では **呼ばれていない**（files_read 空）。read 自体の成功例は判断層 Gemma 020948Z 側の資料にある（本監査ではその JSON を再読していない → 資料上は動作確認済み、本監査では未再確認）。

### run_test

- `execute.run_test`: `[sys.executable, "-m", "pytest", "tests/test_main.py", "-q"]`, `cwd=workspace`, timeout 30s
- 戻り: command, stdout, stderr, exit_code, traceback（結合テキストに `Traceback` が含まれるとき）, execution_time
- **passed/failed だけにはしていない**

`subprocess.TimeoutExpired` は `run_command` で捕捉していない。timeout 時は `dispatch` の包括 `except` に落ち、exit_code 付きの実行結果にはならない。

### run_program

- `[sys.executable, "main.py"]`。同様。

### apply_patch

- 入力: `path`, `content`
- 処理: **ファイル全体の上書き**（unified diff ではない）
- 新規ファイル作成可（親ディレクトリ `mkdir`）
- ディレクトリへは書けない
- `git_diff_before` / `git_diff_after` を返す。**commit はしない**

コード上成立。パッチ適用「失敗」（内容が意図と違う）は、書き込み例外以外は `ok: True`。

### 系統 3（harness adapters）

`read_file` / `list_files` / `search_files` は `tools.file.workspace`。root は **リポジトリ全体**（`workspace_root()` = `registry/tools.json` のある場所）。実験 fixture への閉じ込めではない。

`experiment_test_source`: 一時ディレクトリで関数を呼ぶ。pytest ではない。TimeoutExpired は捕捉する。

catalog に `apply_patch` は無い。

### 未知 Tool 名

`dispatch`: `{ok: false, error: "unknown_tool:{name}"}`。  
系統 1 では Mapping が名前を付けるため、LLM が存在しない Tool を要求する経路は通常ない。系統 2/3 では LLM 名がそのまま来る。

---

## H. 実コード操作

| 項目 | 判定 | 根拠 |
| --- | --- | --- |
| 対象ファイル特定 | 引数 path + known_files / LLM 指定 | Mapping 経由なら known 外は読めない |
| 意図しないファイル | workspace 外は拒否 | `resolve_in_workspace` |
| ただし上書き範囲 | workspace 内なら任意パスに全文書き込み | `apply_patch` |
| Patch 失敗検知 | 例外とディレクトリ拒否のみ | 内容検証なし |
| Patch 結果記録 | run.json の tool_raw_result、git_diff 文字列 | commit 履歴ではない |
| 変更前後 | git_diff vs 初回 HEAD | パッチ後に add/commit しないため、累積 unstaged |
| 複数回修正の履歴 | Turn ごとの files_changed / patch_rounds | git の複数 commit は無い |
| ロールバック | **未実装** | checkout / reset 呼び出しなし |
| 作業ディレクトリ限定 | 系統 1/2 はコピー先。系統 3 はリポジトリ root | |
| 本番ファイル破壊 | 系統 3 `harness.run_case` が `tools/system/cpu/cpu_status.py` を一時 write | try/finally で復元。例外経路の抜けは今回未証明 |

`apply_patch` にコードフェンス断片を渡すと、**ファイル全体がその断片になる。**  
再判断実験の既存結果（Qwen が `main.py` から import を消した）は、この上書き意味と整合する。本監査では再実行していない。

---

## I. Test

```text
LLM →（Mapping または Tool call）→ run_test → subprocess pytest
```

コード上成立（系統 1/2）。

| 項目 | 系統1 判断ループ最小 | 系統2 再判断 |
| --- | --- | --- |
| pytest | `tests/test_main.py -q` | 同様 |
| python main.py | 初期入力と **パッチ後**。Mapping の `run_test` では `sent_for_tool` が pytest ブロックのみ | パッチ後に両方。LLM の `run_test` 時も program を `test_result` に載せる |
| timeout | 30s。TimeoutExpired 未捕捉 | 同様の execute |
| stdout/stderr/exit | あり | あり |
| traceback 欄 | 結合テキストにマーカーがあるとき全文コピー | 同様 |

初期 Failure は実実行結果を LLM に渡している（人工文字列ではない）。既存結果で確認済み。

**注意:** Mapping 経由の `run_test` と、パッチ後ハーネス Test は **返却文面が違う。**  
前者: `sent_for_tool` → `format_execution_block("run_test", result)`。  
後者: `format_test_failure`（「The test still fails.」+ Exit code 見出し）。

`format_test_failure` はパッチ後専用。LLM がテスト再実行だけを Mapping された場合は使われない。

---

## J. 再判断

| 項目 | 判断ループ最小 | 再判断実験 | PA |
| --- | --- | --- | --- |
| Test 結果が LLM へ戻るか | Mapping run_test またはパッチ後 | パッチ後は必ず。native run_test 時は tool メッセージ | 経路なし |
| 元の Failure 保持 | messages[0] に初期ブロックが残る | 同様 | 単発 |
| 以前の判断 | assistant 本文が messages に残る | 同様 | なし |
| 変更内容 | git_diff は run 末尾。LLM へはパッチ Tool 結果 | パッチ後 feedback に pytest/main。diff は test_result に保存、本文に必ず入るかは test_feedback_user 次第（**入らない**） | |
| 何回目の Test か | `patch_rounds`。LLM へは回数を明示しない | 同様 | |
| 前回修正を LLM が知れるか | パッチ内容は Tool 結果 JSON。全文が 3500 で切れる | 同様 | |
| Test 後に別 Tool を選べるか | 次 Turn の Mapping 次第。固定ルール「N 回失敗で上位」は **無い** | 次 Turn の Tool call 次第 | |

「3回失敗したら上位へ」はコード上 **未実装**。

---

## K. 探索範囲変更

構造:

- 固定探索順（main → helper → config）をハーネスが強制するコードは **無い。**
- LLM が別ファイルを要求し、Mapping / Tool call が `read_file` になれば、次に読める。
- 系統 1 は 1 ファイル/Turn。

阻害:

- Mapping が読取を M2 にする / 別 Tool を選ぶと、探索は広がらない。
- `known_files` は workspace 列挙。config.py がディスクにあれば名前は known。traceback に無くても Mapping 対象にはなり得る。
- Prompt はファイル名を教えない（判断ループ最小）。一覧は `list_files` が Mapping されない限り LLM は知らない。

Cursor 観測（既存資料）: glob で全ファイルを見てから読んだ。系統 1 は LIST_HINT が本文に無いと list しない。

---

## L. 状態管理

独立した ProblemState オブジェクトは **未実装。** 実体は `messages` + `run.json`。

判断ループ最小の run 記録にあるもの:

- turns[].raw_output, mapping_*, tool_*, files_read, files_changed, test_result
- 集約: files_read, patch_rounds, stop_reason, final_git_diff

無い / 弱いもの:

- `initial_failure` と `current_failure` の名前付きフィールド（初期は messages[0] と initial_execution/*.json）
- judgments の構造化リスト
- Turn 番号は `turn_id` としてある
- Extraction / 採用候補 span

会話を切ると状態は消える。永続は JSON ファイル。

---

## M. ログ

後から「なぜこの Tool か」を再構成できるか。

**できること（判断ループ最小 run.json）:**

- Turn ごとの `raw_output`（LLM 判断の一次資料）
- `mapping_candidates` と `mapping_output`
- `tool_name` / `tool_arguments` / `tool_raw_result` / `tool_sent_result`
- `messages.json` で LLM に実際に渡した文面

**できない / 歪むこと:**

- `judgment_interpretation.next_action` は **Mapping の action** であり、LLM の次手要約ではない。Gemma Turn 1 では `"run_test"`。
- Extraction の「どの文を採用したか」が無い。
- 候補と実行の対応は残るので、人間が raw と candidates を見ればずれは復元できる。機械的な `judgment_correct` / `extraction_correct` フラグは無い。

「Tool を呼んだ事実」と「直前の判断」は同一 Turn レコードに並ぶ。対応関係の生データは残っている。解釈欄は Mapping 結果で上書きされている。

---

## N. 安全性

### ファイル破壊

- 系統 1/2: コピーした workspace 内。リポジトリ本番コードは直接書かない（copy_fixture）。
- `apply_patch` は workspace 内ならテストファイル含め全文置換可能。
- 系統 3: 本番 `cpu_status.py` を実験中に置換。finally で戻す。**実験基盤として本番パスを触る。**
- success_case: リポジトリ内 fixture を **読む**（root はリポジトリ）。書き込み Tool は呼んでいない。

### 無限ループ

| 制御 | 有無 |
| --- | --- |
| 最大 Turn | あり（8 / 10 / 12 / 14 / 16 など実験ごと） |
| 同じ Tool 連続 | 無し |
| 同じ Patch | 無し |
| 同じ Test | 無し（Gemma は初期と同じ pytest を Mapping で再実行し得る） |
| 同じファイル無限読取 | 無し（max turns のみ） |
| 同じ失敗 | 無し |
| Tool エラー連続 | 無し |
| 意味不明判断 | mapping_gap → 2 idle で停止 |
| Tool 結果異常 | dump して返す。検証なし |

暴走のハード制限は実質 **max turns と idle 停止**。

### LLM / 環境

- `LLMTimeoutError` は Turn を切る。
- context length 文字列で stop_reason を付ける系統あり。
- pytest timeout の TimeoutExpired は未整理。

---

## O. Cursor との比較

再実験していない。既存 `UPPER_JUDGMENT_EXPERIMENT.md` を参考。

| Cursor 側の観測（既存資料） | 現実験コード |
| --- | --- |
| workspace 探索（glob） | list_files は実装済み。系統1では LIST_HINT が無いと自動では呼ばない |
| ファイル発見 | known_files 列挙はハーネス内部。LLM には初期は出さない |
| コード読取 | read_file あり。Mapping が通れば実行 |
| 依存関係確認 | import 解析 Tool は未実装。読んだファイルを LLM が解釈するだけ |
| 複数ファイルを Test 前に修正 | 系統1は 1 Tool/Turn。系統2は複数 native call + フェンス |
| Test | pytest + main.py あり |
| 結果確認 | パッチ後フィードバックあり。Mapping run_test は文面が薄い |
| Test 失敗後に探索変更 | 構造上は次 Turn で可能。Cursor 当該 run では未観測（資料） |

Cursor と同じでないことを失敗とはしない。差は「探索を LLM が指示しても Mapping が実行しない」点が系統1で大きい。

---

## P. 明確な欠陥

形式は指示書 23 に従う。

---

問題:  
判断抽出層が無く、LLM 全文が Mapping 入力になる。

根拠:  
`judgment_loop_min_experiment/bench.py` が `classify_mapping(raw, known_files)` に `raw` 全体を渡す。`extract_*` 呼び出しは無い。

影響:  
本文の後景（「変更後にテストを再実行」）が TEST_HINT にヒットし、前景のファイル要求より実行され得る。

確実性:  
コード上確認済み。Gemma 既存結果で実際に動作確認済み。

推奨:  
LLM 実験の前に、固定判断と全文ログを分けて Mapping を検証する。本監査では実行していない。

---

問題:  
`judgment_interpretation.next_action` が LLM 判断ではなく Mapping 結果である。

根拠:  
同ファイル `"next_action": execute.get("action") if execute else "NOT_MAPPED"`。

影響:  
ログだけ見ると「モデルが run_test を選んだ」と読める。モデル評価が歪む。

確実性:  
コード上確認済み。Gemma run.json で `"next_action": "run_test"` を確認済み。

推奨:  
解釈欄と Mapping 欄を分離する（本監査では修正しない）。

---

問題:  
inspect 近傍窓（64 文字）のため、ファイル名と要求語が離れると read が実行されない。

根拠:  
`mapping.py` `_near_inspect`。Gemma 候補は helper.py / main.py が M2。

影響:  
「ファイルを読め」という判断が Tool に届かない。

確実性:  
コード上確認済み。既存結果で確認済み。

推奨:  
仮 Mapping のまま LLM 性能を語らない。

---

問題:  
1 Turn 1 Tool（系統1）。複数ファイル確認を同時実行できない。

根拠:  
`_prefer` が 1 件。`dispatch` はループ内で一度。

影響:  
「helper と main を確認」は高々片方だけ実行。残りは次 Turn 依存。

確実性:  
コード上確認済み。同時実行の成功例は系統1には無い（未実行ではなく未実装）。

---

問題:  
`apply_patch` が全文置換であり、断片フェンスでファイルが壊れる。

根拠:  
`workspace.apply_patch` の `write_text(content)`。フェンス抽出は `def ` または `=` を含む本文。

影響:  
部分修正のつもりがファイル破壊。再判断実験の既存 Qwen 観測と整合。

確実性:  
コード上確認済み。既存再判断結果は動作確認済み（本監査未再実行）。

---

問題:  
初期 problem_solving harness が本番 `cpu_status.py` を書き換える。

根拠:  
`harness.run_case`: `tool_path.write_text(case["source"]...)`。`tool_path = tools/system/cpu/cpu_status.py`。

影響:  
実験中断や例外で復元が抜けた場合、本番 Tool が壊れる。対象も実コードデバッグループではない。

確実性:  
コード上確認済み。本監査では実行していない。

---

問題:  
判断層と判断ループ最小で Mapping 選択規則が違う。

根拠:  
層は `executable[0]`（フェンス・TEST が配列前方）。ループ最小は `_prefer`（実行可能な read を優先）。窓は 48 vs 64。

影響:  
「Mapping 実験」と読んでも実装が一つでない。結果を横断比較すると歪む。

確実性:  
コード上確認済み。

---

問題:  
`run_command` が `TimeoutExpired` を扱わない。

根拠:  
`execute.py` `subprocess.run(..., timeout=30)` に except 無し。

影響:  
ハングに近い Test は Tool エラー文字列になり、exit_code/stdout 経路と混ざる。

確実性:  
コード上確認済み。実際の timeout 発生は NOT_OBSERVED。

---

## Q. 潜在的問題

断定しない。

- `dump_result` 3500 文字切り詰めが、長い pytest traceback を LLM から欠落させるか。初期入力は切り詰め無しの `format_execution_block`。Tool 経路の JSON は切れる。実害はケース依存 → 要実測。
- 判断層 `run_test` 時、pytest 結果は Investigation JSON、追加の `python main.py` は `test_result` には入るが LLM 文面に入るかは `format_investigation_result` の JSON 内容次第。欠落の有無は未実測。
- `search_files` の部分一致が短クエリで大量ヒットし、切り詰めと相まって誤誘導するか。
- git 未 commit のため、パッチ成功後に `git_diff` が全変更の塊になり、ロールバック点が無い。
- 系統 3 のファイル Tool がリポジトリ全体を読めること（秘密・本番ソース）。書き込み catalog は無いが read は広い。
- mapping_harness_validation が未実行のまま残っている。SUT を import するだけでも、将来誤って既存実験を実行するリスクは運用上の話（コード上は既存実験を書き換えない）。

---

## R. 実装されていないもの

- 単一の Agent 判断ループ（本番接続）
- 判断の構造化抽出（問題 / 仮説 / 不足情報 / 今の次手）
- 今すぐ vs 後で の区別
- 正式 Mapping / Schema / Controller
- 複数 read のバッチ実行（系統1）
- unified diff / 部分パッチ
- ロールバック
- import グラフ解析 Tool
- 「失敗 N 回で探索拡大」ルール（意図的に無し、というコメントあり）
- GPT ライブ経路
- Extraction 失敗 / Mapping 失敗 / Judgment 失敗を分ける機械フラグ
- 同一 Tool・同一パッチ・同一 Test の繰り返し検知
- Problem Analysis と Solving の接続
- 判断層 Mapping と判断ループ最小 Mapping の単一化

---

## S. 実用性評価

**総合: D（構造的問題あり）**

理由（コード事実）:

1. LLM 能力測定の前に、判断→Tool 接続が既知の誤選択を起こす（P の Gemma 経路）。
2. 抽出層が無く、ログの `next_action` が Mapping で上書きされる。
3. 「システム」が複製の寄せ集めであり、本番とも未接続。

内訳（混同しないため）:

| 部品 | 近い評価 | 理由 |
| --- | --- | --- |
| 隔離 workspace の read/list/search/run_test | B | コード上成立。実測は既存実験に部分的にある |
| パッチ後 Test → LLM | B〜C | 経路はある。全文置換と切り詰めが実用性を落とす |
| 自然言語 Mapping | D | 窓・TEST_HINT・1件選択 |
| 初期 harness（cpu_status） | C〜D | 別問題領域。本番ファイル書き込み |
| PA 単体 | B（分析観測として） | Tool ループとしては未接続 |
| Cursor 比較用 capture | 参考のみ | 実験ループではない |

A（実用的な基盤）にはしない。E（全面再設計必須）にもしない。Tool 実行と隔離コピーは残せる。直すべきは接続層である。

---

## T. 実験開始前に修正すべきもの

本監査は修正しない。次作業の候補として優先度だけ書く。採用は人間判断。

1. **判断と Mapping と実行をログ上で分離する。** `next_action` に Mapping 結果を入れない。
2. **LLM 無しで Mapping 単体検証**（固定文・過去 raw 全文・複数行動文）。既存実験は変更せず専用ディレクトリ。未実行の `mapping_harness_validation` があるが、完了とはしない。
3. その検証で「正しい判断 → 別 Tool」が再現するなら、**その Mapping のままモデル比較しない。**
4. 本番 `cpu_status.py` を書き換える harness を、実コードデバッグ評価に使わない。

Mapping の「正しさ」の正式仕様は、今回の監査だけでは決めない。

---

## U. 実験開始しても結果を歪めにくいもの

以下は、目的をその範囲に限れば、基盤欠陥で結論が逆転しにくい。

- Problem Analysis 単体（Tool 無し、出力観測）。ただし「問題解決能力」とは読まない。
- 既存一次資料の **本文** を人間が読む（Gemma がファイルを要求した、等）。Mapping 欄は使わない。
- Native Tool Calling の「API が tools を受け付けるか」（圧縮実験の Gemma 400 等）。接続層の仮 Mapping とは別事実。
- 隔離 workspace の pytest が実エラーを出すこと（初期 execution JSON）。

---

## V. 次に確認すべき事項（監査だけでは足りない）

本監査終了後は実験へ進まない。確認後に次作業を決める、という指示に従う。

監査だけでは確定できないこと:

1. 固定判断文だけを現 Mapping に渡したとき、`read_file(helper.py)` になる割合（コード上は近傍 inspect ならなりそうだが未実行）。
2. 過去 Gemma raw 全文を再入力したとき、既存 run と同じ `run_test` になるか（ロジック上はなるはず。回帰として未実行）。
3. Mapping を通さず `dispatch(read_file, helper.py)` したときの返却文が次 LLM 入力として足りるか。
4. `format_test_failure` と `sent_for_tool(run_test)` の情報差が再判断を変えるか。
5. TimeoutExpired 経路の実際の戻り値。
6. 系統2で LLM が `read_file` を正しく呼んだ事例の一次資料再読（再判断は読取 0 だった、という既存報告）。

---

## 付録: 系統横断表

| 系統 | LLM | Extraction | Mapping | Tool 実装 | Test 再投入 | 本番接続 |
| --- | --- | --- | --- | --- | --- | --- |
| PA | chat | なし | なし | なし | なし | なし（llm.chat のみ） |
| harness catalog | chat + JSON | JSON parse | なし（LLM が名前） | adapters = リポジトリ Tool + temp test | final 時 test_source | cpu_status.py 一時書込 |
| success_case | chat | ファイル言及+語 | NL→read/list | リポジトリ file tools | なし | なし |
| 判断層 | chat 本文 | なし（本文=入力） | 仮 classify | 隔離 copy | パッチ後 / mapped run_test | なし |
| 判断ループ最小 | 同上 | なし | 別の仮 classify | 隔離 copy | 同上 | なし |
| 再判断 / 実コード | native or JSON | tool_calls | なし | 隔離 copy | パッチ後必須 | なし |
| 圧縮実験 | native vs text | tool_calls | なし | 隔離 copy | 実験依存 | なし |
| 上位判断 | Cursor 外部 / GPT 未接続 | — | — | capture のみ | 親が確認 | なし |

---

## 監査の自己制限

- 実験・pytest・Ollama・install は行っていない。
- 既存実験コード・結果・設定は変更していない。
- 本ファイルは新規作成のみ。
- 改善実装・Schema・Controller・本番接続は行っていない。
)