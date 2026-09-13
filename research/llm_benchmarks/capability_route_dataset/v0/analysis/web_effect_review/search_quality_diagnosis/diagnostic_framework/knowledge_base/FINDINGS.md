# FINDINGS

実験事実に根ざした知見。各 Finding は **主張（解釈を含む場合あり）** と **観測** を分け、確度を付ける。

---

## Finding ID: F001

**主張:**  
Qwen3:8b は十分なコードを渡しても、処理経路の帰属（特に stdout 要約と LLM handoff）を誤る場合がある。

**観測:**  
code_reading / spec / route 実験で、`summarize_tool_result`（約 L520）を LLM 経路と取り違えるケースが繰り返し報告された。一方で入口・backend・`rank_hits_for_query` はしばしば正しく認識された。

**根拠:**  
`runs/20260824_082857/code_reading_experiment/EXPERIMENT_REPORT.md`  
`runs/20260824_093317/spec_experiment/EXPERIMENT_REPORT.md`  
`runs/20260824_194421/spec_experiment_v2/EXPERIMENT_REPORT.md`

**確度:** High  

**注意:** すべての読解が失敗するという意味ではない。

---

## Finding ID: F002

**主張:**  
診断ハーネスの `num_ctx` が小さい（例: 4096）場合、コードが実質プロンプトに乗らず「コード不足」と誤認されうる。

**観測:**  
早期フレームワーク／自己検証まわりでコード抜粋不足が原因扱いされ、後の 32768 実験では主要記号がプロンプトに実在することが確認された。

**根拠:**  
`runs/20260824_170527/self_verify/SELF_VERIFY.md`  
`runs/20260824_082857/code_reading_experiment/EXPERIMENT_REPORT.md`（プロンプト実在確認節）

**確度:** High  

**注意:** Ollama の「利用可能 ctx」はモデルにより 32768 指定でも足りない場合がある（F010）。

---

## Finding ID: F003

**主張:**  
「コード上に処理が存在する」ことと「その処理が今回の症状の原因である」ことは別であり、小型LLMはしばしば混同する。

**観測:**  
原因診断で compact_hit 切り詰め・ranking 存在・技術クエリ分岐などを strong 扱いした例。N2 YES でも誤因果は残る。

**根拠:**  
`runs/20260824_082857/.../EXPERIMENT_REPORT.md`（TEST-C）  
`runs/20260824_212236/n2_execution_path_gate/EXPERIMENT_REPORT.md`

**確度:** High  

**注意:** —

---

## Finding ID: F004

**主張:**  
FACT / OBSERVED / INFERENCE / UNKNOWN の明示分離は、ログ未添付時の OBSERVED 捏造抑制に有効である。

**観測:**  
H2_B（ログなし）で OBSERVED=なしを守れた。一方、FACT のみからの原因候補列挙（過信）は残った。

**根拠:**  
`runs/20260824_205442/ranking_filter_log_evidence_experiment/EXPERIMENT_REPORT.md`

**確度:** High（捏造抑制） / Medium（原因全体の正しさは保証しない）  

**注意:** ラベルを使っても原因リストを埋めようとする行動は残る → N3 仮説。

---

## Finding ID: F005

**主張:**  
N2（実行経路存在ゲート）は、経路外処理を原因候補から落とす安全弁として設計上有望だが、経路上の誤因果は排除できない。

**観測:**  
当該ランの自由生成に経路外偽原因が無く NO≈0。compact_hit 切り詰め等の経路上誤因は通過。明示フル経路（TEST-C）は過信増加。

**根拠:**  
`runs/20260824_212236/n2_execution_path_gate/EXPERIMENT_REPORT.md`

**確度:** Medium（効果の定量はシード依存で未完） / High（限界の記述）  

**注意:** 偽原因シードでの再現率測定は未実施（N2b）。

---

## Finding ID: F006

**主張:**  
処理経路単位のコード分解は、stdout と LLM 受け渡しの接続テスト改善に有効な場合がある。

**観測:**  
route_decomposition で print_tool_result と messages.append を別接続として答えられた条件があった。caller 誤認・原因過信は残存。

**根拠:**  
`runs/20260824_195842/route_decomposition_experiment/EXPERIMENT_REPORT.md`

**確度:** Medium–High（当該設問セット）  

**注意:** collect と ranking を同一パックにすると混同が再発しうる。

---

## Finding ID: F007

**主張:**  
仕様書（設計地図）は経路の物語理解を一部助けるが、実装行の正しい帰属を保証しない。

**観測:**  
spec_experiment で Agent/dumps の言葉は増えたが 520 混同は残った。v2 原則追加でも最重要項目で明確優位なし。仕様のみでは実装行を答えられない構造は維持可能。

**根拠:**  
`runs/20260824_093317/spec_experiment/EXPERIMENT_REPORT.md`  
`runs/20260824_194421/spec_experiment_v2/EXPERIMENT_REPORT.md`

**確度:** High  

**注意:** 仕様への意図レベル漏洩（本文取得しない等）には注意。

---

## Finding ID: F008

**主張:**  
collect filter と ranking を別 route pack にすると、混同再発防止と段階帰属の精密さに寄与しうる。

**観測:**  
明示設問では混在でも「別処理」と答えられる場合がある。分離は q6 行帰属などに差。同一 ROUTE_4 混在は以前の同一視失敗と関連しうる。

**根拠:**  
`runs/20260824_205442/ranking_filter_log_evidence_experiment/EXPERIMENT_REPORT.md`  
`runs/20260824_195842/route_decomposition_experiment/EXPERIMENT_REPORT.md`

**確度:** Medium（条件付き）  

**注意:** —

---

## Finding ID: F009

**主張:**  
DeepSeek-Coder-V2 16B への単純置換では、Qwen3 の主要失敗（stdout/LLM、存在＝原因）は十分に解消しない。長い診断プロンプトは ctx 制約で失敗しうる。

**観測:**  
同一設問の A/D は成功。B/C/E 全文は超過。適応短縮後もログ捏造・過信が残った。結論は Method-specific 主。

**根拠:**  
`runs/20260824_234729/model_comparison_deepseek/COMPARISON_REPORT.md`

**確度:** High  

**注意:** 短文の接続 Yes/No では DeepSeek が部分的に勝つ場面あり（trade-off）。

---

## Finding ID: F010

**主張:**  
Cursor 上の大型LLM（Composer）による独立診断は、同一問題について Qwen3 より経路追跡・偽原因棄却・UNKNOWN 利用で良好だった。ただし自己診断全般への一般化と自動修正は未検証／禁止相当。

**観測:**  
条件Bで dumps 経路・collect/rank 分離・本文GET棄却などをコード照合で正しく整理。AUTO-FIX NOT_ALLOWED。

**根拠:**  
`runs/20260825_124200/large_llm_search_web_diagnosis/COMPARISON_REPORT.md`  
`.../CONDITION_B_INDEPENDENT_DIAGNOSIS.md`

**確度:** Medium–High（search_web 当該問題セット）  

**注意:** 一回の診断セッションであり、盲検再実験や他 Tool への一般化は未実施。

---

## Finding ID: F011

**主張:**  
「小型LLMで局所解析 → 構造化候補 → ゲート → 大型LLMで統合」は、現状の証拠から **有望な仮説** である（確定アーキテクチャではない）。

**観測:**  
小型は入口発見・ログ列挙に強み。大型は接続と偽原因棄却に強み。DeepSeek 単独置換は不十分。ハーネス手法が両モデルに効く。

**根拠:**  
F001, F006, F009, F010 および各 COMPARISON/EXPERIMENT_REPORT  

**確度:** Medium（仮説）  

**注意:** 二段パイプラインそのものの A/B 実験は未実施。

---

## Finding ID: F-NH2-1

**主張:**  
Change Request + History Validator による exact 過去State再Active禁止は、Goal に限らず Claim / Hypothesis にも実験的に一般化できる。正当再評価には REOPEN_WITH_EVIDENCE 例外が必要。

**観測:**  
run 20260826_190000: judgment=Supported (generalization); Cond C FA=0 FR=0; Cond D FA=0 FR=0.

**根拠:**  
`runs/20260826_190000/nh2_state_transition_generalization/EXPERIMENT_REPORT.md`

**確度:** Medium（scripted Request・実験用Manager）  

**注意:** 本番仕様ではない。near-exact・evidence品質は未解決。

---

## Finding ID: F-NH3-1

**主張:**  
exact再Active禁止は表記ゆれですり抜けうる。normalization（NFKC/空白/句読点/casefold）はSafetyを改善し、別意味の新Goalを過剰拒否しない（実験範囲）。

**観測:**  
H-NH3-1=SUPPORTED, H-NH3-2=SUPPORTED.

**根拠:** `runs/20260826_191500/nh3_state_safety_boundary/`

**確度:** Medium  
**注意:** 本番仕様ではない。語尾揺れはUNKNOWN。

---

## Finding ID: F-NH3-2

**主張:**  
REOPENのevidence文字列/ID提示だけでは架空証拠を防げない。 registry実在確認と内容照合でFalse Acceptが減る。

**観測:** H-NH3-3=SUPPORTED, H-NH3-4=SUPPORTED.

**根拠:** 同上

**確度:** Medium  
**注意:** 実験用mock registry。

---

## Finding ID: F-NH4-1

**主張:** 形態素/同義ルールによる再Active検出は安全性を上げうるが、類似の新Stateを誤拒否しうる（安全側バイアス）。NFKC+UNKNOWNの方がFRが低い。

**観測:** H-NH4-1=PARTIALLY_SUPPORTED, FR_increase=NO.

**根拠:** `runs/20260826_201500/nh4_state_safety_boundary/`

**確度:** Medium  
**注意:** 実験用ルール辞書。本番辞書ではない。

---

## Finding ID: F-NH4-2

**主張:** Evidenceは exists / content / freshness を分離すべき。 content一致でも state変更前の古い証拠や stale フラグはREOPENに使えない。

**観測:** H-NH4-2=SUPPORTED.

**根拠:** 同上

**確度:** Medium

---

## Finding ID: F-NH4-3

**主張:** sidecarは全部入り不要。test+runtime+evidence_status が最小有効候補。 hash/exec/timestampはUNKNOWN/追加拒否用の拡張。

**観測:** minimal=D (test + runtime + evidence_content), H-NH4-3=SUPPORTED.

**根拠:** 同上

**確度:** Medium

