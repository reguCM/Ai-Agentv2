# Phase O：連続開発タスク実証テスト

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_184709_phase_o_continuous_development`  
**Production 変更:** 0  
**新規 C3:** 0  
**`standard_workflow` 既定値:** `facet_discovery="off"`（未変更）  
**判定:** `PARTIAL_PASS`

## 目的

新しい Reasoning Core / Graph / RAG / Knowledge Base は作らない。

現在ある構造だけで、

```text
ユーザー要求
→ Goal Abstraction
→ Gate
→ Conditional Discovery
→ Coverage Overlay
→ Relevant Facet Routing
→ Research Reuse
→ Decision Support
→ Tool / 実装要求
→ 実装
→ テスト
→ 結果
→ 次の要求
```

が、複数回の要求変更を伴う連続タスクでどこまで持つかを実測する。

壁に当たることは失敗の隠蔽対象ではなく、今回の成果である。

## 実施内容

1 セッションで O-1 から O-8 を順番に流した。技術 A は実在 OSS に固定せず、既存 fixture `RR-A` / LibA を **RECORD** として使った。実機・live Web・Docker / URSim には接続していない。

既存 Workflow の既定は変えていない。連続セッションだけ `facet_discovery="conditional"` と `facet_routing="relevant"` を渡した。

不足を埋めるために追加したのは Experimental Adapter のみ。

| もの | ラベル | 役割 |
|------|--------|------|
| fixture `RR-A` 投入 | RECORD | live TDA が無いので、O-1 後に ResearchRecord を置く |
| `session_research_handoff` | EXPERIMENTAL | Workflow が空の Spec しか出さないとき、session の ResearchRecord から候補を戻す |
| `spec_to_experimental_tool` | EXPERIMENTAL | Tool Spec → `ai_tool/experimental/liba_demo_tool/` の fixture コード |
| `implementation_handoff` | EXPERIMENTAL | 判断に必要な情報の列挙、テスト実行、O-8 の変更評価（コードは書き換えない） |
| `python_version_delta` | EXPERIMENTAL | 「3.12ではなく3.13」を first-match より置換側で読む。Workflow には未接続 |

## 「できた」と「できることが確認できた」

| 表現 | 意味 |
|------|------|
| **できた** | このセッションで、その段が実際に通った |
| **できることが確認できた** | 既存構造または小さな Adapter で、その段が成立し得ると測れた。常時そう動くとは言わない |

Workflow 既定のまま Production で実装まで流せる、とは言わない。

---

## 1. どこまで通ったか

Goal Abstraction → Gate → Conditional Discovery → Coverage →（条件付き）Routing → Decision Support は、調査系の手番では **できた**。

O-6 の Code と Test は、Workflow 単体ではできない。Experimental Adapter を足したうえで **できた**。

O-8 は既存 Tool を参照し、コードを勝手に書き換えず、変更要否を Unknown のまま残すところまで **できた**。

最終判定は `PARTIAL_PASS`。小さな Adapter なしでは実装段に届かない。Adapter を足せば届く。新しい Core は不要だった。

## 2. どこで壁に当たったか

| 壁 | 手番 | 橋渡し | 内容 |
|----|------|--------|------|
| A | O-5 | あり | Discovery は feasible / safe / correct を出さない。判断に必要な情報の列挙は Adapter |
| B | O-1 以降 | あり | 空 store と「その技術A」では Workflow が Tool Spec を作れない。session の ResearchRecord から回復 |
| C | O-6 | あり | Spec の既定は「user implements manually」。Code は Adapter が書く |
| D | O-6 | あり | Test 結果は Workflow に戻らない。`session.last_test_result` へ Adapter が書く |
| E | O-7 | なし | 「3.12ではなく3.13」が first-match で 3.12 のまま。3.12 証拠ありとして full reuse 相当になり、3.13 を再確認しない |
| F | O-3 以降 | なし | session の `last_python` は残る。Coverage の Facet 一覧からは Python / OS が消える |
| G | — | 発生せず | Generic Docker から URSim を推測しなかった |
| H | — | 発生せず | Discovery が安全性・実行可能性・正確性の判定を始めなかった |

失敗の分離:

| 種類 | 実測 |
|------|------|
| 既存構造の不足 | 壁 A〜F。Reuse が「その技術A」を bind しない。Spec→Code が無い。Version 置換の first-match |
| 実装環境の不足 | live Web / 実 LibA / 実機は使っていない。不足であって、今回は fixture で代替した |
| Research不足 | O-1 の ResearchRecord は live 調査ではなく fixture RECORD |
| 仕様不足 | Spec の provenance は execution-verified ではない。実 API の存在は未検証。`api_notes` は空 |

## 3. 各 Facet の引き継ぎ

実測（Coverage が出した ID。session キーとは別）。

| 手番 | Required | Candidate / Keep | Unknown | slot |
|------|----------|------------------|---------|------|
| O-1 | `external_evidence` のみ | なし | なし | — |
| O-2 | `python_version`, `environment`, `external_evidence` | なし | なし | Python 3.12 |
| O-3 | `os` | なし | なし | Windows |
| O-4 | `docker`, `storage` | なし | なし | — |
| O-5 | `environment`, `evidence` | なし | なし | — |
| O-6 | （Discovery Skip） | — | — | — |
| O-7 | `python_version`, `version`, `conflict`, `environment` | `cuda`, `license`, `LibA` | なし | **Python 3.12**（置換失敗） |
| O-8 | `python_version` | なし | なし | Python 3.13 |

保持できたもの（その手番の要求として）:

- O-2 で Python 3.12 を Required にできた
- O-3 で Windows を Required にできた。Docker を Required にしなかった
- O-4 で Docker を Required にできた。URSim は付けなかった
- O-7 で Docker を再 Required しなかった

失われたもの:

- O-1 で API Facet を取りこぼした（「利用できるAPI」が `\bapi\b` に当たらない）
- O-3 以降、Coverage 上から `python_version` が消える
- O-4 以降、Coverage 上から `os` が消える
- 回復 Adapter は LibA 候補の environment を丸ごと戻す（CUDA / GPU まで含む）。必要部分だけの再利用ではない

推測しなかったもの:

- CUDA / License を O-2 で Required にしなかった
- O-3 で Docker を Required にしなかった
- O-4 で URSim を付けなかった
- O-5 で feasible を出さなかった

## 4. Research 検索回数

| 手番 | live Web Search | 備考 |
|------|-----------------|------|
| O-1〜O-8 | **すべて 0** | `tda=None`。実検索はしていない |
| O-1 | fixture 投入 1 件 | RECORD。検索ではない |
| O-7 | `searches_estimate` 0 | 3.12 が covered と見なし EARLY_EXIT_FULL_REUSE |

「検索しなかった」は「再利用が正しく効いた」ではない。Reuse ラベルはほぼすべて `no_reuse`。live クエリを打たなかっただけである。

## 5. Reuse 率

Reuse Efficiency（follow-up 7 手番のうち、Reuse 成功または実装 Skip）: **0.14**

内訳: O-6 が Gate Skip で検索 0 になった分だけを成功と数えた。O-2〜O-5 / O-7 / O-8 の `assess_reuse` は `no_reuse`。

理由: 既存の bind は「前に調べたA」や文頭「Aを」を想定する。「その技術A」は bind しない。

「過去 Research を再利用できることが確認できた」は、以前の Phase（「前に調べたAをPython 3.12で…」）の話である。今回の文言では **できなかった**。

## 6. 不要 Facet の混入

Irrelevant Suppression: **1.00**  
False Discovery 手番: **0**

- CUDA / License を O-2 で Required にしていない
- Docker を O-3 で Required にしていない
- URSim を O-4 で Required / Routing していない
- O-5 の Required は `environment` と `evidence` のみ（大量発明なし）

O-4 の `storage` は Docker の既存 companion で付く。UR 製品 Docker との混同ではない。

回復 Adapter 側の候補 environment に CUDA / GPU が入るのは、Discovery の False Discovery ではなく **丸ごと回復** の副作用である。

## 7. Unknown 維持

- O-3 まで Docker を Required にしない（発明しない）は **できた**
- fixture の Unknown「Python 3.13: no official information」を、O-7 の first-match が **使わなかった**（3.12 側を covered と見た）
- O-8 の変更要否は `UNKNOWN` のまま。推測で Yes/No を埋めなかった
- O-5 は判定せず、必要な情報だけ列挙した

「Unknown を維持できることが確認できた」のは O-8 の変更要否と、O-3 の Docker 非発明である。O-7 の 3.13 Unknown は **維持できなかった**。

## 8. Version Isolation

| 経路 | 結果 |
|------|------|
| 既存 Coverage / `plan_follow_up` | **失敗**。slot は 3.12。`changed_facets` 空。3.12 証拠で足りると見た |
| Experimental `python_version_delta` | **置換を読めることが確認できた**（3.12 → 3.13）。Workflow 未接続 |
| O-8（3.13 だけを書く要求） | slot は 3.13。`changed_facets` に `python_version`。既存 Tool の runtime 3.12 との差を検出 |

3.12 の証拠を 3.13 に流用する規則は作っていない。O-7 の問題は流用規則ではなく、**置換文を 3.12 要求として読むこと**である。

## 9. 実装まで到達したか

**Adapter 経由では到達した。Workflow 単体では到達しない。**

できたこと:

- session の ResearchRecord から Tool Spec（`tool_liba`, runtime Python 3.12, license Y）を回復した
- Spec の runtime / license / tool_name を Experimental コードへ渡した
- `ai_tool/experimental/liba_demo_tool/client.py` を生成した（fixture。実 LibA ではない）

できなかったこと（既存構造）:

- O-1 時点の Workflow は candidates 空で Spec を出さない
- Spec は「人が手で実装する」前提のまま

これは **既存構造の不足** であり、Research不足（実 API 不明）とは別である。実 API が分かっていても、Workflow は Code を書かない。

## 10. テストまで到達したか

**Adapter 経由では到達した。結果の Workflow 帰還は Adapter の session 書き込みである。**

- in-process テスト 3 件成功（JSON object、array 拒否、不正 JSON 拒否）
- live ネットワークなし、実機なし
- O-8 は `last_test_result` を参照できることが確認できた
- O-8 はファイルハッシュを変えなかった（勝手なコード変更なし）

## 11. 次に作るべきもの

Core ではない、小さな Adapter / パターン追加に留める。

1. 会話ポインタ「その技術A」「前回」を `session.last_research_id` へ bind する（推測で別技術を当てない）
2. 「AではなくB」の Version 置換を first-match より優先する（`python_version_delta` の接続。既定 Workflow は off のまま）
3. Coverage が session の `last_python` / `last_os` を Candidate（Required にしない）として残す
4. Test 結果を次手番の材料にする session フィールド（既定経路は変えない）
5. 「利用できるAPI」のような日本語隣接を API alias に足すかどうかは、Phase N+2 の K 計測を壊さない範囲だけ検討する

## 12. 作らない方がよいもの

- Reasoning Core
- Graph / Matrix
- RAG / Vector DB / Knowledge Base
- Discovery への feasible / safe / correct / build
- Production Tool / Registry 接続
- Generic Docker から URSim を出す規則
- Python 3.12 の証拠を 3.13 にコピーする規則
- Unknown を LLM で埋める層
- 今回の fixture クライアントを「実 LibA が使える」と見なすこと

---

## 手番ごとの記録（要約）

### O-1 最初の要求

「ある技術Aについて、利用できるAPIと基本的な使い方を調べたい。」

- Goal: L0 調査、L3 justified
- Gate: `RESEARCH_REQUIRED`（調べたい）
- Discovery: Policy D `REQUIRED`
- Required: `external_evidence` のみ。API 取りこぼし
- ResearchRecord: fixture `RR-A` を RECORD 投入
- Reuse: `no_reuse`（store が空の時点で評価）
- Spec: Workflow 空 → Adapter が回復

### O-2 条件追加

「その技術AをPython 3.12で使えるか調べて。」

- Required に `python_version`。CUDA / License / Docker は Required にしていない
- slot Python 3.12
- Reuse ラベルは `no_reuse`（bind 失敗）。全件 live 再検索はしていない（tda なし）
- 前回情報の「Coverage 保持」は、この手番では Python 新規 Required として出せた

### O-3 環境追加

「Windows環境ならどう？」

- Required: `os`。Docker は Required にしない
- Python 3.12 は session には残る。Coverage 一覧からは消える（壁 F）

### O-4 方法変更

「Dockerを使う場合はどう？」

- Required: `docker`（と companion `storage`）
- URSim なし。Generic Docker と製品 Docker を混同していない
- Windows / Python は Coverage 上は消えたまま

### O-5 実装可能性の調査

「では、これをToolとして作れそう？」

- Gate は `RESEARCH_NOT_REQUIRED` でも、Policy D は `作れそう` で Discovery 起動
- feasible / safe / correct / build は出さない
- Adapter が列挙した判断材料: runtime, license, environment, input, output, error_handling, test_method
- API は Spec の `api_notes` が空のため列に入っていない（仕様不足）

### O-6 実装要求

「では、そのToolを実際に作ってテストして。」

- Discovery Skip、Gate 早期終了。ここが最大のテストポイント
- Adapter が session Spec から Experimental コードを生成し、テスト成功
- Production コードは未変更

### O-7 条件変更

「Python 3.12ではなくPython 3.13の場合だけ確認し直して。」

- 期待: 3.13 だけ再確認。実測: slot 3.12、`changed_facets` 空、Docker は再 Required しない
- keep に `python_version` / `cuda` / `license`（3.12 側の再利用）
- 壁 E。Adapter 単体では置換を読めるが、未接続

### O-8 実装結果の再評価

「Python 3.13へ変更した結果、作成したToolに何か変更が必要？」

- Version 変更を検出（Tool runtime 3.12 vs 要求 3.13）
- 既存 Tool を参照
- 変更要否 `UNKNOWN`
- コード自動変更なし
- 変更案: 3.12 の証拠を 3.13 に使わない。編集前に runtime を再確認する

---

## 評価指標

| 指標 | 値 | 読み |
|------|-----|------|
| ① Required Recall（平均） | 0.83 | O-1 の API 取りこぼしで 0。O-2〜O-5 / O-7 は 1.00 |
| ② Irrelevant Suppression | 1.00 | 不要 Required の混入 0 |
| ③ Reuse Efficiency | 0.14 | 今回の文言では bind 失敗が主因 |
| ④ Search Reduction | live 0 | tda なし。Reuse 成功とは区別する |
| ⑤ Context Retention | 部分 | その手番の slot は立つ。次手番の Coverage からは落ちる |
| ⑥ Version Isolation | as-is 失敗 / Adapter 成功 | O-7 が本丸 |
| ⑦ Unknown Preservation | 部分 | Docker 非発明と O-8 Unknown は維持。O-7 の 3.13 は維持失敗 |
| ⑧ False Discovery | 0 | URSim / CUDA Required 化なし |
| ⑨ Implementation Handoff | Adapter で True | Workflow 単体は False |
| ⑩ Test Feedback | Adapter session で True | Workflow 帰還は無し |

## ラベル

```text
REUSE     :  pretends-not. 今回の文言では assess_reuse はほぼ no_reuse
RECORD    :  fixture RR-A、session last_test_result、壁の記録
EXPERIMENTAL : session handoff / spec→code / version delta
DEFER     :  API alias の日本語隣接、Coverage の session keep
REJECT    :  新 Core、O-8 の自動コード改変、Production 接続
```

## 回帰

Phase F ADOPT（c3=0）、Conditional Discovery 統合、Skip Policy、Coverage、Routing の既存テストは維持。`facet_discovery` 既定は off のまま。
