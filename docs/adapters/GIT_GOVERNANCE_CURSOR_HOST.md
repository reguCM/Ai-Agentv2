# Cursor Host User Rules — Git Governance 同期チェックリスト

**Status:** `HUMAN_SYNC_CHECKLIST`（リポジトリ外の Cursor User Rules は自動検証されない）

**verification_status:** `HOST_ADAPTER_NOT_VERIFIED`（CI は Host User Rules を実測しない）

**contract_version_expected:** `2026-09-12.3`

**last_canonical_review:** `2026-09-12`（G4.1 / G5 checklist 更新）

**機械正本:** `ai_tool/policy/git_governance.json`  
**意味正本:** `docs/GIT_OPERATION_POLICY.md`

Host 上の User Rules（例: `committing-changes-with-git`, `creating-pull-requests`）を更新する際、
次が **project canonical intent（G2/G3/G4.1）** と整合しているか人間が確認する。

## committing-changes-with-git

| 項目 | Canonical intent |
|------|------------------|
| デフォルト commit | 明示指示または `AUTO_COMMIT_ALLOWED` 相当の authorization のみ（Option C） |
| Hook 失敗後 | **`git commit --amend` を Agent が使わない** → 新規 commit で修正 |
| amend 一般 | Human Approval 必須（contract: `amend`） |
| `git reset --hard` | **Agent 禁止**（contract: `AGENT_ALWAYS_BLOCK` / G4.1） |
| `restore` / `clean` / worktree 削除 | guard `local_safety v2.2` で Probe 後のみ（raw CLI / shell は未強制） |
| `Remove-Item -Recurse -Force`（repo 配下） | **自動実行しない**（RULE_ONLY；git_guard 非対象） |
| 秘密ファイル | commit しない（contract: `stage_deny_path_globs` + git_guard） |

## creating-pull-requests

| 項目 | Canonical intent |
|------|------------------|
| push | Verified safe normal push → auto allow（v2.1）；unsafe → BLOCK；unresolved → Human Approval |
| force push / reset --hard | Agent 禁止（Human は Agent 経由で override しない） |

## 同期が不要な場合

User Rule が上記より **厳しい**（例: 常に明示 commit のみ）場合は、Cursor 追加制約として維持してよい。
User Rule が **緩い**（無条件 auto commit 等）場合は Canonical に合わせて更新する。

## 証拠

同期したら Cursor 設定の変更日を記録する（任意）。機械証拠は G5 drift test 候補。
