# Matrix Entity / Source 不整合の保存防止

**日付:** 2026-08-31  
**依頼:** 別 Entity の情報を query Entity の事実として保存できる穴を塞ぐ。10 GB の原因推測はしない。  
**実行主体（実装・テスト・Report・再取得）:** Cursor  
**ingest / retract actor:** `matrix_pipeline`（LLM なし）  
**Run:** `runs/ai_tool/20260831_095000_matrix_entity_source_guard`  
**Server:** `LocalAgentChat/0.15`  
**判定:** `PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Chat Research: **NOT CONNECTED**  
Chat Matrix Write: **NOT OBSERVED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**  
Git commit: **していない**

---

## 修正した原因（コード上確認できたものだけ）

`extract_records_from_hits` は `entity = entity_from_query(query)` を **すべての hit** に付けていた。そのため Search が RTX 5000 / RTX 4000 のページを返しても、VRAM 値が `entity=RTX 3060` のレコードとして `matrix_write` できた。

保存直前に Entity ↔ Source の照合は無かった。Normalize は単位表記のみで、この不整合を検出しない。

10 GB の発生経路は前回どおり **CAUSE: NOT DETERMINED**。今回も推測していない。

---

## 既存データ

`records.jsonl` の既存行は削除・上書きしていない。整理は `runs/matrix/retractions.jsonl` への追記。通常検索は retraction 済み ID を除外する。

retract 直後の sha256（再取得前）: `e68126296978ad04e6caf5904c229b600ffc37455028724a0ae15007d1a50324`（15756 bytes）。retract 前後で同一。

| Value | 処理 | 理由 |
| ----- | ---- | ---- |
| 8 GB | 維持 | 出典 RTX 3060。検索に残る |
| 12 GB | 維持 | 出典 RTX 3060。検索に残る |
| 10 GB | 整理（retract） | `VALUE_NOT_SUPPORTED`。CAUSE = **NOT DETERMINED** |
| 16 GB | 整理（retract） | **ENTITY_SOURCE_MISMATCH**（source RTX 5000） |
| 20 GB | 整理（retract） | **ENTITY_SOURCE_MISMATCH**（source RTX 4000） |

対象 ID: `mr-9ef26e060032` / `mr-43089f3d9495` / `mr-7be71a20ed81`。JSONL 上の行は残っている。`get_by_id` / 経路追跡は可能。

---

## 再発防止

`ingest_web_to_matrix` の **matrix_write 直前**。

1. 出典 title/URL から Entity を取る（query は使わない）
2. 出典 Entity が query Entity と明らかに違う → `ENTITY_SOURCE_MISMATCH` → **書かない**
3. VRAM 値が fetch 本文（なければ excerpt）上で `page_supports_fact` できない → `VALUE_NOT_SUPPORTED` → **書かない**（正しい値へ置換しない）
4. 一致する Wikipedia は snippet に数字があっても wikitext を fetch して再検証する
5. 別 GPU ページの fetch はしない

Search が別 GPU を返すこと自体は異常ではない。保存しないことが成功。

---

## 再取得（実測）

Cursor が `ingest_web_to_matrix("RTX 3060")` を実行。ingest `ing-20260831_004931-dec6d86c`。LLM なし。

| 段階 | 実測 |
|------|------|
| SEARCH | success。hit_count 5 |
| FETCH | Wikipedia RTX 3060 wikitext。成功 |
| EXTRACT | drafts あり |
| NORMALIZE | 単位正規化のみ |
| ENTITY/SOURCE VALIDATION | status=`filtered`。accepted 4 / rejected 3。mismatch 3。unsupported 0 |
| MATRIX_WRITE | success。4 件 |

拒否（保存していない）:

- cited_by RTX 5000 → ENTITY_SOURCE_MISMATCH
- cited_by RTX 4000 → ENTITY_SOURCE_MISMATCH
- cited_by RTX 2000 → ENTITY_SOURCE_MISMATCH

保存した VRAM: **8 GB / 12 GB**、source `https://en.wikipedia.org/wiki/RTX_3060`。10 / 16 / 20 GB は新規保存されていない。検索結果にも出ない。

再取得後 `records.jsonl` は 17630 bytes（追記。既存 10/16/20 行は残置）。

`cited_by` RTX A6000 は GPU 正規表現が `RTX`+数字のため mismatch と判定できず保存された。VRAM 事実ではない。今回は正規表現を広げていない。

---

## ブラウザ

処理タブ Matrix パネル:

```text
SEARCH
→ FETCH
→ EXTRACT
→ NORMALIZE
→ ENTITY/SOURCE VALIDATION
→ MATRIX_WRITE
```

拒否時は `MATRIX_WRITE SKIPPED reason: ENTITY_SOURCE_MISMATCH`（今回の再取得は一部拒否＋一部成功のため WRITE success + check status filtered）。

属性検索から 8 / 12 GB の「出典ページを開く」「照合する」。MATCH = ページ上に記述を確認したこと。真実性の自動確定ではない。

開発タブ: 本 Run / Report / Test。Machine Test: NOT AVAILABLE。

---

## Test

Cursor Report: `tests/ai_tool/chat_interface` + `tests/ai_tool/matrix` **86 passed**。

| ID | 内容 | 判定 |
|----|------|------|
| A | 一致出典から 12 GB を保存 | PASS |
| B | 3060 検索 + 5000/16GB・4000/20GB は書かない | PASS |
| C | 既存 8 / 12 GB 検索 | PASS |
| D | 出典は 3060 だが本文が支持しない 10 GB は書かない（正しい値へ変換しない） | PASS |
| E | retraction は JSONL を書き換えず検索から除外 | PASS |
| 既存 | store / verify / trace / HTTP | PASS |

```text
Machine Test: NOT AVAILABLE
```

---

## 誰が何をしたか

| 主体 | 内容 |
|------|------|
| Cursor | 実装、pytest、retract、再 ingest、Report、ブラウザ操作 |
| Local Agent LLM | 未使用。未接続 |
| search_web / Wikipedia API | 再取得時の Search / Fetch |
| Matrix | retract 3 件（sidecar）。新規 8/12 GB と cited_by を追記 |
| ブラウザ | 処理タブで経路・検索・出典・照合を確認 |

---

## 未観測

| 項目 | 判定 |
|------|------|
| 10 GB の元の発生原因 | NOT DETERMINED |
| 10 GB がテスト投入だったこと | 事実として扱っていない |
| LLM / Cursor が 10 GB を入れたこと | NOT OBSERVED |
| RTX A6000 cited_by を mismatch と判定できなかったことへの追加修正 | 今回しない |
| Chat 経路の Matrix Write | NOT OBSERVED |
| Cursor live | NOT OBSERVED |

---

## Git

コミットしていない。未変更: `agent.py`, `pipeline.yaml`, `search_web` 本体, `AGENT_VISIBLE_DEFAULT`, ResearchRecord, Chat 通常回答経路。
