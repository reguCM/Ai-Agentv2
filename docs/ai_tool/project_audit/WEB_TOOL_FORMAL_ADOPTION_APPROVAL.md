# Web Tool Formal Adoption — Human Review Approval

**Phase:** Human Review / Approval Phase  
**Date:** 2026-08-28  
**HEAD at approval:** `875cc47` — `ai-agent: freeze current development state`  
**Prior review:** [WEB_TOOL_FORMAL_ADOPTION_REVIEW.md](./WEB_TOOL_FORMAL_ADOPTION_REVIEW.md)  
**Security:** [WEB_TOOL_SECURITY_REVIEW.md](./WEB_TOOL_SECURITY_REVIEW.md)  
**Status:** **APPROVED — Implementation Phase authorized**  
**Production changes this phase:** **NONE**  
**Git commit this phase:** **NONE**

---

## 1. 承認サマリ

| Tool | Purpose | Decision |
|------|---------|----------|
| `search_web` | **Discovery** | **APPROVED** — Registry 正式登録（Implementation Phase） |
| `read_url_text` | **Fetch** | **APPROVED** — experimental → 正式 Registry（Implementation Phase） |

**Rename `search_web_include_mean`:** **NOT REQUIRED**（Phase 2 結論を維持）

---

## 2. Human Review Decisions

### HR-1 — search_web Registry 正式登録

**Decision: APPROVED**

| 条件 | 状態 |
|------|------|
| Discovery 責務維持 | ✅ 承認条件 |
| output shape 変更なし | ✅ 承認条件 |
| 意味理解機能を Tool に追加しない | ✅ 承認条件 |
| Search Tool を Research Engine 化しない | ✅ 承認条件 |
| network safety review 結果維持 | ✅ 承認条件 |

**Implementation Phase で実施:** WT commit + Registry `visibility=agent` + Agent schema 公開

---

### HR-2 — read_url_text 正式昇格

**Decision: APPROVED**

| 条件 | 状態 |
|------|------|
| SSRF boundary 維持 | ✅ |
| HTTP/HTTPS のみ | ✅ |
| localhost / private 拒否 | ✅ |
| response size limit 維持 | ✅ |
| output shape 変更なし | ✅ |
| HTML raw 等は known limitation | ✅ 文書化済み |

**Implementation Phase で実施:** Registry 正式登録 + overlay 依存整理

---

### HR-3 — search_web output

**Decision: APPROVED / NO INTERFACE CHANGE**

正式 output:

```json
{
  "query": "string",
  "hits": [{"title", "snippet", "url", "backend"}],
  "backends_tried": [],
  "error": null | "string",
  "fetch_limit": number,
  "return_limit": number,
  "candidates_collected": number
}
```

Search 結果の高度な意味解析・要約は **追加しない**。

---

### HR-4 — read_url_text output

**Decision: APPROVED / NO INTERFACE CHANGE**

正式 output keys: `ok`, `url`, `final_url`, `status_code`, `content_type`, `size_bytes`, `content`, `truncated`, `error`

HTML readability 改善は **別 Phase**。

---

### HR-5 — System Prompt ↔ Registry 整合

**Decision: APPROVED**

正式採用後、Agent 公開 Tool と System Prompt の期待 Tool 一覧を **一致させる**。

**制約:** Prompt 変更は Registry 変更と **同一 Implementation Phase** で行う。本 Approval Phase では変更しない。

---

### HR-6 — Search → Fetch workflow

**Decision: APPROVED**

正式 basic Web workflow:

```text
User → LLM → search_web → 検索結果 → LLM URL選択
     → read_url_text → 本文 → LLM → 回答
```

- 複数 round Tool Calling: **許可**（既存 `MAX_TOOL_ROUNDS` 維持 — 勝手に変更しない）

---

### HR-7 — Research Tool

**Decision: DEFERRED**

現時点では新 Research Tool を **作成しない**。

将来候補（`search_web` 肥大化禁止）:

- 複数 query 生成
- 複数ページ自動収集
- 情報比較 / 引用管理
- research planning / 結果統合

---

## 3. 正式採用後 Tool 責務（固定）

| コンポーネント | 責務 |
|----------------|------|
| `search_web` | Discovery |
| `read_url_text` | Fetch |
| LLM / Agent | Meaning / Reasoning / Selection |
| Research Tool | 将来必要時のみ（HR-7 DEFERRED） |

> Tool に「意味理解」を詰め込むことを目的にしない。LLM が query を生成するのは正常な責務分担。

---

## 4. Compatibility

| Tool | 変更種別 | Interface |
|------|----------|-----------|
| search_web | Agent visibility: 未公開 → 正式公開 | **NO CHANGE** |
| read_url_text | experimental overlay → 正式 Registry | **NO CHANGE** |

**Breaking change:** 意図的な output breaking change **なし**  
**Capability expansion:** Agent から新 Tool が見える — **Agent capability expansion** として扱う

---

## 5. Security 条件（Implementation Phase でも維持）

### search_web

- 外部検索 API の network access のみ
- filesystem write なし

### read_url_text

- SSRF / localhost / private / HTTP(S) only / size / timeout / redirect 安全

**Security boundary 変更 → 別途 Human Review 必須**

---

## 6. Implementation Phase 引き継ぎチェックリスト

### search_web

- [ ] WT implementation 確認
- [ ] spec 確定（output 現状維持）
- [ ] selective commit
- [ ] Registry 正式登録
- [ ] Agent schema 公開
- [ ] System Prompt 整合（HR-5）
- [ ] Safety regression

### read_url_text

- [ ] Registry 正式登録
- [ ] experimental bridge 依存整理
- [ ] Agent schema 確認
- [ ] SSRF テスト回帰

### 共通

- [ ] deterministic tests
- [ ] live LLM E2E
- [ ] Search → Fetch E2E
- [ ] tool selection / execution / result utilization
- [ ] safety / regression
- [ ] Git selective commit

---

## 7. 本 Phase の変更禁止 — 遵守確認

| 対象 | 変更 |
|------|------|
| agent.py | ❌ |
| registry/tools.json | ❌ |
| tools/system/network/* | ❌ |
| production_bridge.py | ❌ |
| System Prompt | ❌ |
| Git commit | ❌ |

---

## 8. 最終状態

```text
HR-1 search_web Registry adoption     APPROVED
HR-2 read_url_text formal adoption    APPROVED
HR-3 search_web output                APPROVED / NO INTERFACE CHANGE
HR-4 read_url_text output             APPROVED / NO INTERFACE CHANGE
HR-5 Prompt ↔ Registry alignment      APPROVED (Implementation Phase)
HR-6 Search → Fetch workflow          APPROVED
HR-7 Research Tool                    DEFERRED

Production changes:  NONE
Registry changes:    NONE
Agent changes:       NONE
Git commit:          NONE

STOP:                YES
Next phase:          Web Tool Formal Adoption — Implementation Phase
```

---

## 関連

- [WEB_TOOL_FORMAL_ADOPTION_REVIEW.md](./WEB_TOOL_FORMAL_ADOPTION_REVIEW.md)
- [TOOL_LIFECYCLE_POLICY_CANDIDATE.md](./TOOL_LIFECYCLE_POLICY_CANDIDATE.md)
- [WEB_TOOL_RESPONSIBILITY_MATRIX.md](./WEB_TOOL_RESPONSIBILITY_MATRIX.md)
