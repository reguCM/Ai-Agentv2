# Agent Task Decomposition Evaluation

## 1. 目的

ローカルLLMをAI-Agentとして利用する際、

- 大きな仕事をそのまま渡す方式
- GoalとTaskを分解し、小さい実行単位で順番に処理させる方式

のどちらが安定するかを確認する。

今回の評価結果を、今後のAgent Runtime設計の判断根拠として残す。

---

# 2. 評価対象

主に以下のローカルモデルで確認した。

- Gemma4 12B
- Qwen3 14B
- Gemma4 E4B（一部比較）

利用した主なTool：

- `search_files`
- `list_files`
- `read_file`
- `get_system_summary`

---

# 3. 大きな依頼を直接渡した場合の観測

Git read-only Tool群の設計・既存構造調査など、複数の確認事項を含む比較的大きな依頼を直接渡した。

その結果、以下の問題を確認した。

## 3.1 Toolを使わず一般論で回答する

Agentとしての前提を明示しない場合、

- workspaceを実際に調査しない
- 存在未確認のRegistry名やファイル名を推測する
- Tool Result Contractを読まずに準拠したつもりになる

などの挙動が発生した。

---

## 3.2 Agent前提を与えるとTool利用は改善

ユーザー発言側で、

- 単なるチャットLLMではなくLocal Agentとして行動する
- workspace依存情報は推測せずToolで確認する
- 検索だけで終わらず必要なファイルを読む

という前提を与えると、実際にTool Callingが発生した。

確認された流れ例：

`list_files`

または

`search_files → list_files → read_file`

まで進行した。

このため、Agentとしての役割定義は有効と判断する。

---

# 4. 大きな依頼で確認された問題

## 4.1 Goal Drift

ファイル調査中に、本来不要な

`get_system_summary`

を呼び出し、最終回答までCPU・GPU・Memory情報へ逸脱するケースを確認した。

このため、

「現在のGoalと未完了Taskを毎回保持する仕組み」

が必要と判断する。

---

## 4.2 同一失敗の繰り返し

存在しないパスに対して、

`read_file → path_not_found`

を複数回繰り返すケースを確認した。

新しいEvidenceが増えていないにもかかわらず同種Actionを再試行していた。

このため、

- Failure履歴保存
- Stagnation判定
- 同じActionの抑制
- 別Recovery Actionへの切替

が必要と判断する。

---

## 4.3 長時間処理・Timeout

大きなTask分解要求では、90秒以内にLLM応答が終了せず、

`LLMTimeoutError`

が発生した。

後のターンで前の回答が流れてくるケースも確認されたため、

- 自動強制終了を基本としない
- LONG_RUNNING状態をUI表示する
- ユーザー停止ボタンを用意する
- CANCELLED Turnの遅延応答を破棄する
- Turn Isolationを行う

必要性が確認された。

---

# 5. Tool Result Contract修正版の確認

修正版File Toolを使用した環境では、

通常成功：

```text
ok: true
status: success
error: null
warnings: []
```

上限到達時：

```text
ok: true
status: partial
error: null
warnings: [...]
```

が確認された。

旧形式の

```text
ok: true
error: 上限到達
```

よりも、AgentがResultの意味を判断しやすくなった。

また、`partial` 後に別Toolへ切り替えて処理を継続する挙動も確認できた。

---

# 6. 小Task方式の評価

大きなGoalを小Taskへ分割し、

- Goal
- 現在Task
- 完了条件
- Evidence
- Failure履歴

を明示してLLMへ渡す方式を試験した。

---

# 7. Test A: Completion判定

## Task

Tool Result Contract v1の必須フィールドを、実ファイルを読んで確認する。

## 完了条件

候補ファイルを検索しただけでは未完了。

`read_file` によって実際の内容を確認する必要がある。

## 結果

Tool実行：

`search_files → partial`

`search_files → partial`

`read_file → success`

LLMは最終的に、

`Task status: COMPLETE`

と判断した。

必須フィールド：

- `ok`
- `status`
- `error`
- `warnings`

を抽出できた。

## 評価

PASS

検索成功だけをTask完了とせず、`read_file`まで進んだ。

---

# 8. Test B: Evidence引継ぎ

## 前Task Evidence

Tool Result Contract v1の必須フィールド：

- `ok`
- `status`
- `error`
- `warnings`

## 次Task

このEvidenceだけを利用して、`git_status` ToolのResult Schema案を作る。

Tool使用は禁止。

## 結果

LLMはToolを使用せず、前Task Evidenceを再利用した。

以下を含むSchema案を作成した。

- staged
- unstaged
- untracked
- partial対応
- Tool Result Contract必須4フィールド

## 評価

PASS

前TaskのEvidenceを次Taskへ引き継ぐ方式が有効であることを確認した。

---

# 9. Test C: Recovery Action選択

## 状態

以下のパスはすでに失敗済み。

- `tools/file/read_file.py`
- `tools/file/list_files.py`
- `tools/file/search_files.py`

すべて `path_not_found`。

`tools/` 自体は存在する。

## Task

同じ失敗を繰り返さず、次に行うRecovery Actionを1つ選ぶ。

## 結果

LLMは、

`tools/ ディレクトリのファイル一覧を取得する`

を選択した。

理由：

`tools/file/` という仮定が失敗したため、1段上のディレクトリ構造を確認して正しいパスを特定する。

## 評価

PASS

Failure履歴を渡すことで、同じ失敗の再試行を避け、別経路を選択できた。

---

# 10. Test D: Replan

## 初期Task計画

- T1 Tool Registry確認
- T2 Tool Result Contract確認
- T3 File Tool実装確認
- T4 git_status実装
- T5 git_diff実装
- T6 git_branch_info実装
- T7 単体テスト
- T8 Local Agent Tool Calling確認

T1〜T3はCOMPLETE。

## 新Evidence

- File Toolにはworkspace境界チェックが存在する
- Git Toolにもworkspace外アクセス防止が必要
- 初期計画にはGit Tool用workspace境界確認Taskが存在しない

## 結果

LLM：

`Replan status: REQUIRED`

と判断。

T3とT4の間に、

`Git Toolのworkspace境界チェック仕様を定義する`

Taskを追加した。

完了済みT1〜T3は維持された。

## 評価

PASS

途中EvidenceからTask不足を発見し、必要最小限のTask追加と順序変更ができた。

---

# 11. 評価結果まとめ

| 評価項目 | 結果 |
|---|---|
| Agent前提によるTool利用改善 | PASS |
| partial後の処理継続 | PASS |
| 小Task Completion判定 | PASS |
| Evidence引継ぎ | PASS |
| Recovery Action選択 | PASS |
| Replan | PASS |
| 大Taskを直接処理 | 不安定 |
| Goal維持 | 要改善 |
| 同一Failure抑制 | Runtime側支援が必要 |
| 長時間Task | Lifecycle改善が必要 |

---

# 12. 採用する主要Agent動作

今後のAgent主要動作として、以下を採用する。

```text
User Request
↓
Goal登録・保存
↓
Task Decomposition
↓
Task順序保存
↓
現在TaskをLLMへ提示
↓
Small Action
↓
Tool / LLM Result
↓
Evidence保存
↓
Completion判定
↓
Progress / Stagnation判定
↓
必要ならRecovery
↓
必要ならReplan
↓
次Task
↓
Goal達成判定
↓
Final Synthesis
↓
最終回答
```

---

# 13. 基本設計方針

LLMに大きな仕事全体を保持・実行させない。

プログラム側で以下を保持する。

- Goal
- Task一覧
- Task順序
- Current Task
- Completion Condition
- Evidence
- Failure History
- Progress State
- Open Questions
- Replan結果

LLMには、その時点で必要な小さい判断・実行だけを渡す。

前Taskの結果が必要な場合は、保存済みEvidenceをHINTとして渡す。

---

# 14. 再計画方針

初期Task分解を固定しない。

途中で得られたEvidenceを基に、

「現在のTask一覧だけでGoalを達成できるか」

を再評価する。

不足があれば、

- Task追加
- Task順序変更
- 再調査
- Recovery

を行う。

完了済みTaskは、必要な理由がない限りやり直さない。

---

# 15. 結論

今回の実測では、

「大きな仕事をLLMへ直接渡して自律実行させる方式」

よりも、

「Goal・Task・Evidence・Failureをプログラム側で管理し、小さいTask単位でLLMへ渡す方式」

の方が明確に安定した。

特に、

- Completion判定
- Evidence再利用
- Recovery
- Replan

について良好な結果が得られた。

このため、

**Goal保存 → Task分解 → 小Task実行 → Evidence保存 → Completion判定 → Recovery → Replan → 最終統合**

を、今後のLocal AI-Agentの主要動作ループとして採用する。