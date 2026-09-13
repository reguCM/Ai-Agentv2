# Git Operation Policy v1

## 1. 目的

本Policyは、AI-Agent開発におけるGit操作の安全性、一貫性、追跡可能性を確保することを目的とする。

特に、Cursor、Codex、AntiGravity、Local Agentなど複数のAI開発支援環境を利用する場合でも、次を追跡できる状態を維持する。

- 現在どのbranchで作業しているか
- 何を変更したか
- どのテストを通したか
- どこまでcommit済みか
- master/mainへ何を統合したか

基本思想は次のとおりとする。

**feature branch内では作業を進めやすくし、共有・統合・破壊的操作ではHuman Approvalを要求する。**

## Machine Contract Reference

意味と運用の叙述は本書を正本とする。Agent 向けの承認区分（action ID）は次の機械契約に従う。

| 項目 | 正本 |
|------|------|
| 機械契約 | `ai_tool/policy/git_governance.json` |
| Policy Manifest 参照 | `ai_tool/policy/development_policy.json` の `distribution.git_governance_ref` |
| 期待 contract version | `2026-09-12.3`（更新時は本表と機械契約を同時に改訂） |

Human Decision 要約（詳細は機械契約）:

- Commit Option C: 無条件 auto commit 禁止 / `AUTO_COMMIT_ALLOWED` 時のみ LEVEL 2 可
- G4.1: Agent は `git reset --hard` を実行しない（`AGENT_ALWAYS_BLOCK`）。Human の直接操作は Agent 契約外

機械契約全文を本書へ複製しない。

## 2. 基本原則

### 2.1 master / mainを直接開発場所にしない

通常の実装・修正・実験はfeature branchまたはstabilize branch上で行う。

原則としてmaster/mainへ直接コード変更を行わない。

### 2.2 1つのbranchでは1つの主要テーマを扱う

例:

- Agent Runtime
- Recovery Integration
- Tool Result Contract
- Test Runner
- UI改善

異なる目的の変更を可能な限り同一branchへ混在させない。

軽微で直接関連する修正は同じbranch内で扱ってよい。

### 2.3 commitは「戻せる作業単位」とする

commitはファイル数ではなく、1つの意味ある変更単位で作成する。

良い例:

- Agent Runtime State追加
- current_tool仕様修正
- Tool Result Contract v1追加
- File ToolsをContract v1へ適合
- Chat UIのTool一覧をRegistry連動化

避ける例:

- Runtime、UI、Model変更を1commitへ混在
- 大量の無関係な修正をまとめる
- 作業途中で壊れている状態を無理にcommitする

## 3. 作業開始時の必須確認

AIがGit管理されたプロジェクトで作業を開始する場合、最初に次を確認する。

1. 現在branch
2. HEAD
3. staged files
4. unstaged files
5. untracked files

既存変更がある場合、それを今回の作業によるものと決めつけてはならない。

既存変更は原則として保持する。

## 4. Git操作の権限レベル

### Agent 向け機械契約（Machine Contract）

Agent（Cursor / Codex / Local Agent による自動 Git 操作）について、**意味と運用の叙述は本書を正本**とし、
**action ごとの承認区分**は次の機械契約に従う。

- `ai_tool/policy/git_governance.json`（Policy Manifest 参照: `ai_tool/policy/development_policy.json` の `git_governance_ref`）

**Commit（Option C）:** Agent は無条件に auto commit しない。Task / Goal / Execution から
`AUTO_COMMIT_ALLOWED` が明示されている場合に限り、下記 LEVEL 2 の条件をすべて満たすとき commit してよい。

**Amend:** `git commit --amend` は Human Approval 必須とする。pre-commit / pre-push 等の Hook 失敗後に
Agent が `--amend` してはならない（修正は新規 commit とする。Human が直接 amend する場合は §5 の承認手順に従う）。

**reset --hard（Agent）:** Agent は `git reset --hard` を実行しない（機械契約 `AGENT_ALWAYS_BLOCK`）。
Human が直接必要とする場合は Agent 経路を使わず操作する（Agent 向け Human Approval 経路は設けない）。

### LEVEL 1 — 自動実行可能

feature / stabilize branch内では、次をAIが自動実行してよい。

- `git status`
- `git diff`
- `git diff --check`
- `git log`
- `git show`
- `git branch --show-current`
- 履歴・差分調査
- commit対象候補の分類
- commit messageの作成

また、`AUTO_COMMIT_ALLOWED` が明示され、後述 LEVEL 2 を満たす場合に限り、次も自動実行可能とする。

- `git add`（§7 の明示 path 規則に従う）
- feature branch内での`git commit`

### LEVEL 2 — 条件付き自動実行

#### feature branchでのcommit

`AUTO_COMMIT_ALLOWED` が有効な場合に限り、次をすべて満たすときのみ自動実行可能とする。

1. 作業目的が明確
2. 対象変更が完成している
3. 必要なテストがPASS
4. `git diff --check`がPASS
5. 無関係な変更がcommitへ混入しない
6. 既存の他作業変更を誤ってstageしない
7. commit内容を説明できる

条件を満たす場合、AIは対象ファイルだけをstageし、commitしてよい。

#### 新規feature branch作成

次の条件で自動作成可能とする。

- master/main以外から不要な派生をしない
- 現在の未commit変更を失わない
- 新しい作業テーマが既存branchと明確に異なる
- branch名が目的を表す

ただし、未commit変更が存在し安全にbranch変更できない場合は自動切替しない。

## 5. Human Approval必須操作

次の操作は、必ず人間の明示承認を得てから行う。

- master/mainへのmerge
- master/mainへの直接commit
- remoteへのpush
- Pull Request作成・merge
- branch削除
- tag作成・削除
- revert
- cherry-pick
- conflict解消を伴う重要merge
- remote branch作成
- historyを書き換える操作

Human Approvalでは、対象branch、対象commit、テスト結果、merge/push対象を簡潔に提示する。

## 6. 原則禁止する操作

通常のAI作業では次を実行しない。

- `git reset --hard`
- `git clean`
- `git push --force`
- `git push --force-with-lease`
- `git rebase --onto`など大規模履歴変更
- 未確認の大量ファイル削除
- 他作業者の変更を破棄する操作

`git reset --hard` は上記 Agent 禁止に従う。Human が直接実行する場合は、理由と影響を説明し、自己責任で行う。

その他（`git clean` 等）でどうしても必要な場合は、理由と影響を説明し、Human Approvalを要求する。

### 6.1 破壊的ローカル操作（Safe Operation Policy v2.2）

Git 標準では `restore` / `reset` / `clean` / path 単位 `checkout` の**実行前 hook は存在しない**。
機械判定は **明示的な git_guard 呼び出し**（`--action local_git` + `--local-op`、設定 `local_safety: v2.2`）で行う。

| 判定 | 例 |
|------|-----|
| **SAFE** | 変更のない path への restore（実質 no-op）、`git clean -n`、index のみの unstage、clean 対象 0 件、登録済み **clean** worktree の通常 `git worktree remove` |
| **BLOCK** | 未コミット変更がある path への `restore` / `checkout -- path`、`reset --hard`（dirty または HEAD 以外）、untracked を消す `git clean -f`、dirty / force worktree 削除 |
| **NEED_HUMAN** | 安全性を Probe できない、`reset --soft` / `--mixed` で ref を動かす等 **意図が機械確定できない** 操作 |

**Agent（Cursor / Codex / Local Agent等）:** リポジトリ配下への `Remove-Item -Recurse -Force` / `rm -rf` 等の再帰強制削除を自動実行しない。
worktree 整理は `git worktree list` で登録を確認し、公式 `git worktree remove` と guard 判定を使う。

stash / reflog での回収可能性だけを理由に、データ破棄を SAFE とみなさない。

## 7. staging規則

`git add .`や`git add -A`など、広い範囲を無条件にstageする操作は原則使用しない。

可能な限り対象ファイルを明示し、今回の作業差分だけをstageする。

既存のunstaged / untrackedファイルが今回の作業と無関係な場合、stageしてはならない。

`.env`、秘密鍵、credential、token等の秘密情報を含む可能性があるファイルはstageまたはcommitしない。
機械的な対象patternは`ai_tool/policy/git_governance.json`の`stage_deny_path_globs`とgit_guard設定を正本とし、
AdapterやHost User Rulesへ別の固定一覧を複製しない。

## 8. commit前確認

commit前には最低限、次を確認する。

### A. Diff

- 意図した変更だけか
- debugコードが残っていないか
- 一時ファイルが含まれていないか
- unrelated diffがないか

### B. Test

変更内容に対応した最低限のテストを実行する。

可能であれば関連する回帰テストも実行する。

テスト階層、E2E Goal Acceptance、Verification Budget、Evidence Reuseの判断は、
`docs/DEVELOPMENT_TEST_POLICY.md`を正本とする。

### C. Git

- branch
- staged files
- unstaged files
- untracked files

## 9. commit message規則

commit messageは、後から目的が分かる簡潔な形式にする。

推奨形式:

```text
<type>: <変更内容>
```

例:

```text
feat: add agent runtime state tracking
fix: clear current_tool after tool execution
test: add agent runtime integration coverage
docs: define tool result contract v1
refactor: align workspace file tools with result contract
```

使用候補:

- `feat`
- `fix`
- `refactor`
- `test`
- `docs`
- `chore`

英語を使用する場合も簡潔な単語を優先する。必要であれば日本語commit messageを使用してもよい。

## 10. branch命名

branch名は作業目的を表す。

例:

```text
stabilize/agent-runtime-step1
stabilize/tool-result-contract
feature/test-runner
feature/recovery-integration
fix/workspace-tool-result
```

推奨prefix:

- `feature/`
- `fix/`
- `stabilize/`
- `refactor/`
- `experiment/`

実験的変更と本番統合前変更を区別する。

## 11. master / mainへの統合条件

master/mainへmergeする前に、原則として次を満たす。

1. branchの目的が達成されている
2. 必要なテストがPASS
3. 重大な既知不具合が残っていない
4. 未完部分がある場合は明示されている
5. unrelated diffが混入していない
6. commit履歴から変更内容を追跡できる
7. Human Approvalを取得する

可能であればmerge前に関連回帰テストを実行する。

## 12. push条件

remoteへのpushは、Git Governance Safe Operation Policy v2.1 に従う。

### 12.1 機械確認済みの通常 push（SAFE NORMAL PUSH）

pre-push hook が次を機械的に確認でき、fast-forward 等の安全条件を満たす場合は、
追加の Human Approval を要求せず push を許可する（Guard PASS）。

- 許可された remote（例: origin URL ポリシー）
- force / ref delete ではない
- pre-push が受け取った remote SHA に対する fast-forward（履歴破壊なし）
- その他 git_guard 設定上の BLOCK 条件に該当しない

未追跡ファイル（例: `runs/_diag_tmp/`）の存在だけを理由に push を止めない
（push 対象は commit 済みオブジェクトのみ）。

### 12.2 Human Approval が必要な push（UNRESOLVED）

安全性を機械的に確定できない、または Policy 上未定義の特殊 push は
NEED_HUMAN とし、人間の意図確認後に進める。

### 12.3 BLOCK される push（KNOWN UNSAFE）

non-fast-forward による履歴上書き、ref delete、禁止 remote、
force push 等は BLOCK する。Human Approval だけで BLOCK を解除しない。

### 12.4 報告（Human 判断が必要な場合）

Human Approval が必要な場合、push前に次を報告する。

- 現在branch
- push対象branch
- HEAD
- 最新commit一覧
- テスト結果
- working tree状態（参考。未追跡のみでは SAFE を否定しない）

## 13. 他のAI・作業者との共存

Cursor、Codex、AntiGravity、Local Agentなど複数の作業者が同じRepositoryを扱う場合、自分が作成していない変更を勝手に修正・stage・commitしない。

既存変更の所有者が不明な場合は、変更内容を確認し、今回の作業と分離し、必要なら報告する。

## 14. 中断・利用上限到達時

AIサービスの利用上限、セッション終了、作業中断が発生する可能性がある場合、可能であれば中断前に次を残す。

- 現在branch
- HEAD
- 完了済み作業
- 未完作業
- テスト結果
- staged / unstaged / untracked
- 次に行う作業

作業が意味のある完成状態で、commit条件を満たしている場合はfeature branch内へcommitしてよい。

壊れた中間状態を無理にcommitする必要はない。

## 15. AIが判断に迷った場合

次の場合はGit操作を止め、人間へ確認する。

- 今回の変更か既存変更か判断できない
- branch切替で変更を失う可能性がある
- conflictが発生している
- master/mainを変更する必要がある
- pushが必要
- reset/revertなどの破壊的操作が必要
- commitに含めるべきファイルを判断できない

## 16. 作業完了報告

Git操作を伴う作業完了時には、最低限次を報告する。

1. branch
2. HEAD
3. 変更内容
4. 実行テスト
5. テスト結果
6. 作成commit
7. staged
8. unstaged
9. untracked
10. master/mainへの統合可否
11. push可否
12. Human Approvalが必要な次操作

テスト結果は`docs/DEVELOPMENT_TEST_POLICY.md`に従い、Component、Integration、
E2E Goal Acceptance、NOT_RUN、およびREUSE / SPOT_CHECK / RERUNを区別する。

## 17. 本Policyの基本判断

通常運用では次のとおりとする。

### feature branch内

**調査・実装・テスト・commitまでAIへ任せてよい。**

### master/main

**統合はHuman Approval必須。**

### remote

**pushはHuman Approval必須。**

### 破壊的Git操作

**原則禁止。必要時はHuman Approval必須。**

これにより、日常的なGit管理の負担をAIへ移しつつ、プロジェクト全体へ影響する重要操作だけを人間が管理する。
