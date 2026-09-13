# Tool Lifecycle Policy — Candidate

**Status:** POLICY CANDIDATE（本書は承認済みポリシーではない）  
**Origin:** Web Tool Formal Adoption — drift 再発防止の記録  
**Date:** 2026-08-28

---

## 1. Lifecycle ステージ

```text
DRAFT
 ↓
IMPLEMENTED
 ↓
TESTED
 ↓
TRIAL
 ↓
HUMAN REVIEW
 ↓
APPROVED
 ↓
REGISTRY
 ↓
AGENT AVAILABLE
 ↓
E2E
 ↓
FORMALLY ADOPTED
```

Tool が途中状態の場合、**状態を明示する**。途中状態を自動的に正式採用済みと扱わない。

---

## 2. 中間状態ラベル

### IMPLEMENTED_NOT_ADOPTED

```text
Implementation = YES
Registry       = NO
Prompt ref     = MAYBE YES
Agent avail    = NO
```

**例（2026-08-28 時点）:** `search_web` — WT に実装、Registry 未登録、Prompt 言及あり

**ルール:** IMPLEMENTED_NOT_ADOPTED を FORMALLY ADOPTED と混同しない。

### PROMPT_REGISTRY_DRIFT

```text
System Prompt が Tool を期待
AND
Registry visibility=agent に存在しない
（または逆: Registry のみで Prompt 未言及）
```

**ルール:**

- **警告対象**として記録
- **自動修正禁止**
- **自動 Registry 登録禁止**
- → Human Review へ

**例（承認前）:** Prompt は `search_web` を想定、HEAD Registry には不在

---

## 3. Web Tool 適用例（承認後の目標状態）

| Tool | 承認後目標 |
|------|------------|
| search_web | REGISTRY + AGENT AVAILABLE + PROMPT 一致 |
| read_url_text | REGISTRY（overlay 卒業）+ AGENT AVAILABLE + PROMPT 一致 |

---

## 4. 自動化の境界

| やってよい | やってはいけない |
|------------|------------------|
| 状態ラベルの監査・記録 | WT を自動 commit |
| drift 検出テスト | 未 HR Tool の Registry 自動登録 |
| Freeze / Review Run | Prompt 自動書き換え |

---

## 5. 関連 HR

Web Tool HR-1 / HR-2 承認により、`search_web` / `read_url_text` は **APPROVED → Implementation Phase へ**。

Lifecycle 上は `APPROVED` 段階。**REGISTRY / FORMALLY ADOPTED は Implementation 完了後。**

---

## 6. 参照

- [WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md](./WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md)
- [CURRENT_STATE_FREEZE.md](./CURRENT_STATE_FREEZE.md)
