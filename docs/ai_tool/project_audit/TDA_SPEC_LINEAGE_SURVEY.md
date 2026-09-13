# 仕様提案系譜 — 調査（実装なし）

**日付:** 2026-08-31  
**実行主体:** Cursor  
**範囲:** 定義→呼び出し→保存→参照→次工程。JSONL 原本は未変更。  
**判定:** 系譜全体は **PARTIAL**。完成した学習システムではない。

Cursor live: **NOT_OBSERVED**（推測で補完しない）  
Machine Test: **NOT AVAILABLE**  
pytest PASS ≠ 仕様が正しかった  
Git commit: **していない**

---

## A. 呼び出し経路（実接続）

```text
要求
 ├─ POST /api/spec/propose ── CONNECTED → propose_specification
 │                              session_id / implementation_id / test_run_id は
 │                              関数引数としてはあるが HTTP が渡さない → NOT_CONNECTED
 ├─ Chat tool_creation/development ── CONNECTED
 │     classify → maybe_record_job → propose_specification(session_id, job_id)
 │     → JSONL 追記 → Job.proposal_id / turns.proposal_id 書き込み CONNECTED
 ├─ Chat chat / research ── propose を呼ばない NOT_CONNECTED
 └─ agent.py ── import なし NOT_CONNECTED

Proposal (origin=llm_proposal)  JSONL 追記 CONNECTED
 ↓
Human Revision  POST /api/spec/revise → append_human_revision
                parent_proposal_id 必須 CONNECTED
                差分レコード専用 origin は無い PARTIAL（親子は残る。difference 欄なし）
 ↓
Implementation  implementation_id は予約。生成・実装フロー接続なし NOT_CONNECTED
 ↓
Test            test_run_id は予約。pytest との結合なし NOT_CONNECTED
                test_observation は旧ライブ1件に null であるだけ。現行 writer は test_run_id
 ↓
Problem         POST /api/spec/problem CONNECTED（親 Proposal へ）
                implementation_id / test_run_id は呼び出し側が渡せば保存。生成しない
 ↓
Correction      人間修正をもう一度追記すれば親子は作れる CONNECTED
                resolution_proposal_id は NOT_IMPLEMENTED
```

Chat 内部の ID（Event に提案 ID がある ≠ 系譜完成）:

```text
run_chat_turn
  Job 作成（proposal より先）
  propose 保存（JSONL に session_id と development_job_id）
  別 correlation_id を stamp（JSONL 内の correlation_id とは別）
  Job.proposal_id を後付け CONNECTED
  session.turns[].proposal_id CONNECTED（第一級。Event だけではない）
  Timeline / dev_cases は proposal_id を読まない NOT_CONNECTED
```

Cursor: `cursor_record` は常に `"NOT_OBSERVED"`。`cursor_connected` は常に false。内部ログ取得経路なし。

---

## B. ID 1対1対応

| ID | 生成場所 | 保存場所 | 参照場所 | 親 | 子 | 状態 |
|----|----------|----------|----------|----|----|------|
| proposal_id | `new_proposal_id()`（LLM/人間/問題いずれも sp-） | JSONL、last.json、Chat Job、session.turns | get_by_proposal_id、GET last、GET proposals、UI last | LLM は null。修正/問題は parent_proposal_id | list_by_parent | CONNECTED（問題も同じ ID 空間。problem_id は無い） |
| request_id | sha256(要求文)[:16]。修正は親を継承（仮仕様） | JSONL | list_by_request_id、GET ?request_id= | 要求文グループ | 同一ハッシュの全 origin | PARTIAL（文言変更で LLM 再提案すると別列） |
| version | 同一 request_id の件数+1 | JSONL | 表示のみ | なし | なし | PARTIAL（出現順。系譜ではない。意味は変更していない） |
| origin | 新規 LLM/人間/問題に書き込み | JSONL | UI、テスト | — | — | CONNECTED（旧ライブ1件は origin 無し。推測で埋めない） |
| parent_proposal_id | 人間修正・問題の writer | JSONL | GET ?parent_proposal_id= | 親 proposal_id | 子一覧 | CONNECTED |
| supersedes | LLM レコードに null を書くだけ | JSONL | なし | — | — | INTERFACE_ONLY |
| human_revision（フィールド） | LLM レコードに null | JSONL | テストが null を確認 | — | — | INTERFACE_ONLY。実体は origin=human_revision の別行 |
| problem（origin） | append_problem_record | JSONL | GET parent 一覧 | parent_proposal_id | なし専用 | CONNECTED。problem_id / resolution_proposal_id / rollback_cost は NOT_IMPLEMENTED |
| assumptions / unknowns / HCR リスト | LLM JSON 正規化 | JSONL | UI、回答文 | — | — | CONNECTED（中身は LLM 自己申告。照合なし） |
| session_id | Chat が propose に渡す | JSONL（Chat経路） | 親から子へ継承可 | session | — | PARTIAL（API propose は渡さない） |
| development_job_id | maybe_record_job | JSONL（Chat）と session.jobs | Job.proposal_id 逆向き CONNECTED | job | — | PARTIAL（Timeline 未参照） |
| correlation_id | propose 内と run_chat_turn で別発行 | JSONL は前者、turns は後者 | stamp_events | — | — | PARTIAL（二重） |
| implementation_id | 呼び出し引数のみ。生成なし | JSONL に null または渡された値 | 子が親からコピー可 | — | — | NOT_CONNECTED（実装フロー無し） |
| test_run_id | 同上 | 同上 | 同上 | — | — | NOT_CONNECTED |
| test_observation | 旧レコードの null フィールド | 旧ライブ JSONL のみ | 現行 writer は使わない | — | — | NOT_CONNECTED |
| cursor_record | 定数 NOT_OBSERVED | JSONL | 表示なし | — | — | NOT_OBSERVED |

---

## C. 不足表

| 項目 | 状態 | 不足理由 | 影響 | 小規模追加可能か |
|------|------|----------|------|------------------|
| Proposal→Job/Session ID | PARTIAL | Chat は書く。Timeline は読まない。API propose は session を付けない | API 経由の案は Chat と結べない | YES（HTTP が引数を渡す。JSONL 書き換え不要） |
| GET by proposal_id | NOT_CONNECTED | store 関数はある。HTTP なし | 系譜を ID で辿る UI/他システムが弱い | YES（GET 追加。原本非破壊） |
| Proposal→Implementation | NOT_CONNECTED | 欄だけ。実装フローが ID を作らない | 実装と仕様が後から結びにくい | 欄は既存。生成器は既存実装フロー調査後。大規模再構成は禁止 |
| Implementation→Test | NOT_CONNECTED | test_run_id 未生成。pytest 非結合 | 「テスト通った」を仕様正しさに誤用しうる | 観測レコード追記は小規模。pytest 本体改変は不要 |
| Problem→Impl/Test | PARTIAL | 親 Proposal は必須。impl/test は任意引数 | 実装中問題が仕様列に乗らないことが多い | YES（渡すだけ）。生成は別 |
| Human→Original 系譜 | CONNECTED | parent_proposal_id | 差分本文は未保存 | 差分追記は小規模 |
| difference / human_reason 専用行 | NOT_IMPLEMENTED | 修正レコードに reason はある。structured difference なし | 後の分析が全文比較頼み | YES（origin 追加。親を書き換えない） |
| supersedes | INTERFACE_ONLY | 常に null。writer なし | 分岐の「どちらを採用したか」が無い | YES（新行にだけ書く） |
| problem_id と proposal_id の分離 | NOT_IMPLEMENTED | 問題も sp- を使う | 一覧が混在。追跡は origin で可 | 任意。必須ではない |
| resolution_proposal_id / rollback_cost | NOT_IMPLEMENTED | 問題レコードに無い | 解決版とのリンクが parent の解釈頼み | YES |
| LLM HCR vs 人間承認 | PARTIAL | リストは LLM 申告。awaiting_human_review はフラグ。HUMAN_CONFIRMED レコードなし | LLM 空リストを承認と誤読しうる | YES（確認追記。親を昇格させない） |
| ASSUMED 自動昇格 | 無し（良い） | 昇格コードは見つからない | — | 追加しない |
| LLM_FAILURE / 正誤 | NOT_IMPLEMENTED | llm_judgment 固定。問題≠失敗 | 原則どおり | 追加しない |
| Policy 項目 human_revision=NOT_IMPLEMENTED | PARTIAL | 新規 LLM 評価が古い文言のまま | 保存データが「修正経路が無い」と嘘を書く | YES（評価文言だけ。旧 JSONL は触らない） |
| Cursor 記録 | NOT_OBSERVED | 取得経路なし | 内部理解を推測してはいけない | 取得可能物が出てから。今は定数のまま |
| 学習方法 | NOT_DETERMINED | 方針どおり | — | 決めない |

---

## D. 実装候補（最大5。今回は未実装）

既存 JSONL を書き換えない。自動正誤・学習・Policy 自動変更はしない。

1. **HTTP propose に session_id / job_id / implementation_id / test_run_id を渡す**  
   なぜ: 関数は既に受ける。API が捨てている。  
   既存データ: 新規行のみ。旧行は null のまま。  
   ロールバック: 引数を無視するだけ。  
   効果: API 経由案も後から実装・テスト ID を載せられる。

2. **GET /api/spec/proposal?proposal_id=**（既存 `get_by_proposal_id`）  
   なぜ: 系譜の点を ID で取る参照が無い。  
   既存データ: 読取のみ。  
   ロールバック: エンドポイント削除。  
   効果: 親子・Job・後続レコードの結合が機械的にできる。

3. **差分観測の追記** `origin` 新種、`original_proposal_id` + `human_proposal_id` + `difference` + `human_reason` + `difference_status=UNKNOWN`  
   なぜ: 修正行はあるが「何が変わったか」が構造化されていない。正誤は書かない。  
   既存データ: 追記のみ。  
   ロールバック: その origin を読まない。  
   効果: 後の傾向分析の原料。今は判定しない。

4. **問題レコードに resolution_proposal_id / rollback_cost を任意追記**  
   なぜ: 問題と修正版のリンクが parent 解釈だけ。  
   既存データ: 新行のみ。原因は引き続き NOT_DETERMINED 可。  
   ロールバック: フィールド無視。  
   効果: 問題≠LLM失敗のまま、解決版だけ辿れる。

5. **人間確認の別 origin**（LLM_REQUESTED と HUMAN_CONFIRMED を混同しない）  
   なぜ: 現状 HCR リストは LLM 申告。フラグは承認ではない。  
   既存データ: 追記。LLM 案の ASSUMED は自動 CONFIRMED にしない。  
   ロールバック: 新 origin を無視。  
   効果: 「確認した事実」を蓄積できる。

推奨順: 2 → 1 → 3。4 と 5 は仕様の細部が残るので人間確認向け。

---

## フィールド実態（3.1）

| フィールド | 定義 | 実際の書き込み |
|------------|------|----------------|
| proposal_id | 有 | 全新規レコード |
| request_id | 有 | 全新規。修正は親継承 |
| version | 有 | 出現順 |
| origin | 有 | 新 LLM/人間/問題。Phase1 ライブ1件は欠ける（推測で埋めない） |
| parent_proposal_id | 有 | 人間・問題のみ。LLM は null |
| supersedes | 有 | 常に null。未使用 |
| human_revision | 有 | LLM 行で常に null。別 origin が実体 |
| problem | origin+本文 | 問題行に problem/cause/cause_status |
| assumptions/unknowns/HCR | 有 | LLM parse 時。意味検証なし |
| llm_judgment | 有 | 常に NOT_IMPLEMENTED |

Policy 評価の `human_revision=NOT_IMPLEMENTED` は **経路ができた後も新規 LLM 行に書き続けている**。部品の嘘。参照して「未実装」と読んではいけない。
