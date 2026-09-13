# Problem Analysis モデル比較（最小 Prompt）

**FA / Schema / 使用モデルの最終決定はしない。**  
完全最小 Prompt を `deepseek-coder-v2:16b` と `qwen3:14b` に同一条件で渡した。

- 実行: `20260831T235618Z`
- ハーネス: `problem_analysis_model_compare_bench.py`（既存 3A/3B/3C ハーネスは未変更）
- 生ログ: `results/problem_analysis_model_compare/20260831T235618Z/`
- Prompt: 3C と同一（`problem_analysis_minimal_bench.PROMPT_TEMPLATE`）
- Failure: 3C と同一（`problem_analysis_bench.CASES`）
- `tools=` なし。`think=` は渡していない

評価は Cursor が `raw_output`（assistant content）を読んだ観測である。正解率ではない。

---

## A. 実験条件

| 項目 | DeepSeek | Qwen3:14b |
| --- | --- | --- |
| Ollama 名 | `deepseek-coder-v2:16b` | `qwen3:14b` |
| Prompt | 同一（Analyze / Do not fix / Do not use tools / Failure） | 同一 |
| A〜E | 同一4フィールド | 同一 |
| temperature（記録） | 0.0 | 0.0 |
| chat() | `model=` + `messages=` のみ | 同一 |
| generation options | `llm.chat` が active profile から setdefault（num_predict 2048, num_ctx 4096） | 同一経路 |
| 順序 | A→E のあと stop | その後 A→E |
| thinking 要求 | なし | なし |
| thinking 観測 | なし（`thinking_observed: false`） | **あり**（5件とも `true`。content とは別フィールド） |

Qwen の thinking は今回の比較軸にしない。PA の比較は `raw_output` のみ。thinking が乗ったことは条件差として記録する。

途中で Prompt / 条件は変えていない。10件とも `call_ok: true`。

---

## B. DeepSeek 結果

保存: `deepseek-coder-v2-16b/case_A.json` … `case_E.json`

**前回 3C の raw_output と5件すべて文字一致。** 全文は 3C（`results/problem_analysis_minimal/20260831T234044Z/`）と同じ。

傾向（3C と同じ）:

| ケース | 概要 |
| --- | --- |
| A | IndexError の言い換え → 原因候補6項（空リスト・ロジック・設定・外部依存等）→ logs/code が要る、checks を置け |
| B | None.items の説明 → データ源 / 誤処理 / API 仮説 → **error handling 追加** |
| C | 3 vs 2 をデータ不足と読む → Conclusion で missing fields を直せば解決 |
| D | CUDA 環境仮説 → **Update Drivers** 等 |
| E | `unknown_tool` をツール未認識と読み、Conclusion で **主因は unidentified tool** と断定 |

骨格: 言い換え → Possible Causes → Recommendations →（しばしば）Conclusion。

---

## C. Qwen 結果

保存: `qwen3-14b/case_*.json`。以下は `raw_output` 全文（thinking は含めない）。

### A（1251 chars）

```text
The failure indicates that the `cpu_status` tool encountered an **IndexError** due to attempting to access a list element at an index that does not exist. This typically occurs when the code assumes the list contains a specific number of elements (e.g., based on system expectations or hardcoded logic), but the actual list is shorter than anticipated. 

### Key Analysis:
1. **Invalid Index Access**: The tool likely tried to retrieve data from a list (e.g., CPU metrics, core information, or status values) using an index that exceeds the list's bounds. For example, if the code assumes a list of 4 CPU cores but the system only reports 2, accessing index 3 would trigger this error.

2. **Data Source Mismatch**: The tool may rely on a data source (e.g., system APIs, hardware sensors, or parsed logs) that returned incomplete or unexpected data, leading to a list with fewer elements than the code expects.

3. **Lack of Bounds Checking**: The code does not validate the list's length before accessing specific indices, exposing it to failures when the input data deviates from assumptions.

This error highlights a logical flaw in the tool's design, where it fails to handle edge cases where the data structure does not meet expected constraints.
```

### B（1156 chars）

```text
The failure indicates that the `data_loader` tool encountered an `AttributeError` when attempting to access the `.items()` method on a `None` object. This suggests that the code expected a dictionary-like object (which has the `.items()` method) but instead received `None` (i.e., a missing or uninitialized value). 

### Key Analysis:
1. **Cause**: The error occurs because the code tried to call `.items()` on a `None` value, which is not a valid object for this operation.
2. **Likely Scenario**: 
   - A variable or object that was expected to be a dictionary (or similar structure) was not properly initialized or returned `None` due to an error in data retrieval, configuration, or logic.
   - For example, a function may have returned `None` instead of an empty dictionary, or a required configuration parameter was missing.
3. **Implication**: The failure highlights a missing safeguard in the code to handle cases where the expected data structure might not be present (e.g., no error checking for `None` before accessing `.items()`).

This is a logical error in the code's assumptions about data structure availability, not a tool-specific issue.
```

### C（480 chars）

```text
The failure indicates a **ValidationError** occurred during validation, specifically due to an **insufficient number of fields**. The validator expected **3 fields** in the input data, but only **2 were provided**. This mismatch suggests the input data is incomplete or does not conform to the required structure. The error does not specify which fields were missing or why the validation criteria required 3 fields, so further context would be needed to pinpoint the exact cause.
```

### D（1649 chars）

```text
The failure indicates that the CUDA runtime initialization process encountered a critical error, preventing the system from accessing GPU resources. This could stem from several potential causes:

1. **Missing or Incompatible CUDA Drivers**: The system may lack necessary CUDA drivers, or the installed drivers may not match the CUDA version required by the application.

2. **Hardware Issues**: The GPU might be disconnected, malfunctioning, or unsupported by the CUDA toolkit. This includes scenarios where the GPU is not properly seated, powered, or recognized by the system.

3. **Environment Configuration**: Environment variables (e.g., `PATH`, `LD_LIBRARY_PATH`) may not correctly point to CUDA libraries, or the system may lack necessary kernel modules for GPU communication.

4. **Resource Conflicts**: Other processes or applications might be monopolizing GPU resources, preventing initialization. This includes conflicts with GPU drivers, virtualization layers, or concurrent usage by other CUDA-enabled programs.

5. **System Compatibility**: The OS version, kernel modules, or hardware architecture (e.g., 32-bit vs. 64-bit) may be incompatible with the CUDA runtime or installed drivers.

6. **Permissions or Security Restrictions**: The user may lack necessary permissions to access GPU resources, or system policies (e.g., SELinux, AppArmor) could be blocking CUDA operations.

7. **Corrupted CUDA Installation**: The CUDA toolkit or runtime libraries may be improperly installed, corrupted, or missing critical components required for initialization.

No further analysis or corrective actions are provided, as per the instructions.
```

### E（1042 chars）

```text
The failure indicates a **RuntimeError** from an unspecified tool ("unknown_tool") with the generic message "operation failed." This suggests that the tool encountered an unexpected condition during execution that prevented it from completing its task. Possible causes could include:

1. **Invalid or unsupported operation**: The tool may have attempted an action that is not allowed in the current context (e.g., invalid input, incorrect state, or incompatible parameters).
2. **Resource constraints**: The operation might have failed due to insufficient system resources (e.g., memory, disk space, or network connectivity).
3. **Configuration or environment issues**: The tool may rely on external dependencies, environment variables, or system settings that are missing or misconfigured.
4. **Unanticipated edge cases**: The tool's logic may not handle certain scenarios, leading to an uncaught exception.

No further details are available to narrow down the root cause, as the tool is unidentified and the error message lacks specificity.
```

---

## D. Model 間比較

`raw_output` のみ。thinking は比較しない。

| 観測 | DeepSeek | Qwen3:14b |
| --- | --- | --- |
| Failure理解 | エラー型の説明はできる。長め | 同様に型の説明。短め。C は mismatch を1段落で書く |
| 情報不足認識 | A 末尾で logs/code。E は generic と認識しつつ主因断定 | **C と E で「これ以上は特定できない」が明確。** A/B は不足より欠陥断定 |
| 不明点の具体性 | どの list / index / 行は出ない | 同様に出ない。A は架空の「4コア vs 2」例を出す |
| 必要情報 | logs / code / config の一般論。D は CUDA 版・driver | C は「どの field が欠けたか」「なぜ3か」。E は詳細不足。A はデータ源一般 |
| 調査方法 | Recommendations 見出しで列挙（修復混在） | 調査手順のリストは弱い。D は原因列挙で止め、修正しないと明記 |
| 原因仮説 | 全件で Possible Causes が主構造 | A/B は Key Analysis、D/E は候補列挙。事実と仮説のラベル分けは弱い |
| 修正への飛躍 | B error handling、D Update Drivers、E logging 実装 | A bounds checking 欠如、B None ガード欠如を指摘。**コードパッチや driver 更新手順は出さない。** D は指示どおり修正しないと書く |
| 根拠のない仮定 | E を未インストール/PATH 問題に接続して主因化。B の API | A の CPU コア数例、センサー。E は unidentified と書くが PATH 断定はしない |
| Failureごとの差 | 中身は変わる。骨格は原因リスト+推奨で固定 | 中身は変わる。C だけ短く不足認識。D は環境。骨格はケースで少し変わる |
| Tool Mapping に使えそうな情報 | D の CUDA/env 項目は対象種になる。A の「どの list」は欠ける | C の「欠けた field / なぜ3」は調査対象になりうる。A の具体識別子は欠ける |

共通: 最小 Prompt では「どの list / どの index / 発生箇所」まで自発的に下りない。Tool 名は出ない。3段（分かる/分からない/調べる）はどちらも見出しにしない。

差: DeepSeek は推奨＝修復に寄りやすい。Qwen の content は短く、C/E で不足を残し、D で修正しないと書く。一方 Qwen A は架空例を事実のように置く。

---

## E. 前回 3C との比較（DeepSeek 再現）

| ケース | 3C raw_output | 今回 DeepSeek |
| --- | --- | --- |
| A〜E | `20260831T234044Z` | **5件とも一致** |

ハーネス差・Prompt差・temperature差として説明する必要はない。同一モデル・同一 Prompt・同一 Failure で content が再現した。

Qwen との差は、その再現済み DeepSeek 傾向との差として扱ってよい。

条件差（再現対象外）: Qwen だけ thinking フィールドが付いた。`chat()` 引数は同じ。Ollama/モデル既定と見る。

---

## F. 設計上の示唆

**観測事実**

- 最小 Prompt の DeepSeek 出力は再実行で一致した。
- 同じ Prompt でもモデルで、修復提案の量・不足の残し方・長さが違う。
- どちらの content も、Mapping 用の「対象 list / index / 行」は自発的に出さない。
- Qwen は thinking を content と別に返した（要求していない）。

**仮説（未採用）**

- 独立した Problem Analysis 段階を置くなら、最小 Prompt だけではモデルによって「仮説+修復」にも「短い不足認識」にも寄る。
- 「未知を具体化させる」ことは、この Prompt ではモデル差より先に **出ていない**。
- thinking を PA 入力に使うかは別実験。今回の比較対象ではない。

Schema / FA / 採用モデルは決めない。

---

## G. 次の候補（実施しない）

今回の結果から必要そうなものだけ。採用ではない。

1. Qwen の thinking を読む / 切る、の差（今回は切っていない）
2. traceback / source を Failure に足した同一2モデル比較
3. 他の既存モデル（qwen3:8b、qwen2.5-coder:7b、gemma3:12b）
4. 「修正するな」を 3B 並みに強くした同一2モデル（Prompt 変更は別実験）

実行: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_model_compare_bench`
