# 第1回結論：機械的 bind / diff / select は成立する。Production にはまだ載せない

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_192046_r1_first_conclusion`  
**Production 変更:** 0  
**新規 C3:** 0  
**`standard_workflow` 既定値:** `facet_discovery="off"`（未変更）  
**総合判定:** `PARTIAL_PASS`  
**機械的経路（Experimental）:** `PASS`

## 評価した構造

今回は「LLM に大量の記憶を読ませて推論させる」方向を評価していない。測ったのは次の経路である。

```text
記憶全体
  → 機械的 bind
  → 機械的 diff
  → 機械的 select
  → 必要な Evidence だけ
  → LLM（解釈・Spec・実装支援の文章化）
```

この構造は **設計候補** として記録する。Reasoning Core / Graph / RAG / Vector DB / Knowledge Base にはしない。

## 実測の要点

| 比較 | 5 Record | 20 Record | 50 Record | 100 Record |
|------|----------|-----------|-----------|------------|
| 全記憶 Facet | 19 | 64 | 154 | **304** |
| LLM へ機械的選択後 | **4** | **4** | **4** | **4** |
| 正しい Record へ bind | できる | できる | できる | できる |
| 無関係 Facet の混入 | 0 | 0 | 0 | 0 |

100 Record 相当（無関係な記憶を大量に混ぜた状態）でも、要求対象 A を 1 件指定すれば LLM へ渡す Facet は 4 のまま。削減率は **0.9868**。

検索最小化:

| パターン | 検索数 | 判定 |
|----------|--------|------|
| 既存 Evidence で足りる（Python 3.12） | **0** | PASS（0 が正しい） |
| 一部だけ不足（Python 3.13） | **1** | PASS |
| 全面的に不足（未bind + 3.13 + CUDA 12.4） | **2** | PASS（全件再検索ではない） |

---

## テスト計画と実施結果

Experimental 経路のみ。Production と既定 Workflow は触っていない。新しい Core は作っていない。

| # | 確認内容 | 判定 | 実測 |
|---|---------|------|------|
| 1 | 記憶量スケール | PASS | 5 / 20 / 50 / 100 Record。A へ bind。slice は常に 4 |
| 2 | Version / 差分再配分 | PASS | 3.12↔3.13、CUDA 12.3→12.4、Windows→Linux、Docker 有り→無し、同時変更 |
| 3 | Follow-up / セッション継続 | PASS | 調査→Py→CUDA→OS→戻す→Docker 追加。過去 Facet は消えない |
| 4 | 曖昧な参照 | PASS | 一意だけ BOUND。それ以外は UNRESOLVED。推測 Bind なし |
| 5 | Conflict / Unknown | PASS | 公式 3.12 / 第三者 3.13 / 未対応を残す。winner なし |
| 6 | Evidence Isolation | PASS | A を 3.13 にしても B の Linux / CUDA 12.4 も C の Docker / URSim も使わない |
| 7 | LLM 入力削減 | PASS | 全記憶 304 → 選択 4。LLM に整理させていない |
| 8 | Search 最小化 | PASS | 0 / 1 / 2。検索 0 は PASS |
| 9 | Goal→…→Decision Support | PASS | 責務は混ぜない。Discovery に feasible / safe / correct なし |
| 10 | 要求→…→Test | PASS | 独立 fixture。既存 liba_demo_tool は上書きしていない |
| 11 | Cursor / Local Agent | PASS | 分担を文書化しただけ。接続は実装していない |
| 12 | 総合判定 | PARTIAL_PASS | 機械的経路は成立。Production 未接続 |

Phase F ADOPT、Phase O / P / P-7 の既存テストは維持。

---

## 1. 記憶量スケール

A〜E の 5 Record に、無関係な filler Record を足して 20 / 50 / 100 にした。1 件の巨大 Record ではない。

要求「その技術Aについて調べて。」（session に `last_research_id=RR-A`）:

- bind: **RR-A**
- 必要 Facet: python_version / os / cuda / license
- URSim / ROS / Node.js / Docker / filler の noise は入らない
- session が無いと UNRESOLVED（推測しない）

**重点:** 記憶が増えても結果は壊れない。壊れるのは「全記憶を LLM に渡す」側であり、機械的 select 側ではない。

## 2. Version / 差分再配分

| 操作 | 再調査 | 保持 | コピー禁止 |
|------|--------|------|------------|
| Python 3.12 → 3.13 | python_version:3.13 のみ | OS / CUDA / License | 3.12 Evidence を 3.13 にしない。3.13 は UNKNOWN |
| Python 3.13 → 3.12 | なし（historical_restore） | CUDA など | 3.13 を 3.12 にしない。3.12 は confirmed |
| CUDA 12.3 → 12.4 | cuda:12.4 のみ | Python | 12.3 を 12.4 にしない |
| Windows → Linux | os:linux | Python / CUDA | A が Windows なら Linux は UNKNOWN |
| Docker 有り → 無し | docker=absent（ユーザー制約） | 他 Facet | 有りの Evidence を無しに流用しない |
| Python + CUDA + Linux 同時 | 変わった Facet だけ | License など | 全件再検索しない |

Conflict は消していない。Unknown を Confirmed へ勝手に変えていない。

## 3. Follow-up / セッション継続

同一 Session で 6 手番:

1. A を調査
2. Python を 3.13 へ
3. CUDA を 12.4 へ
4. OS を Linux へ
5. Python 3.12 / CUDA 12.3 / Windows へ戻す
6. Docker を追加

確認できたこと:

- license など過去 Facet は消えない
- 戻した値は confirmed、途中の 3.13 / 12.4 / linux は historical
- 現在値と historical を混同しない
- 各手番の検索は全件再検索にならない（最大でも不足 Facet 数）

## 4. 曖昧な参照

| 入力 | 結果 | 理由 |
|------|------|------|
| その技術A（session あり） | BOUND → RR-A | session id |
| 前のやつ（session あり） | BOUND → RR-A | session id |
| その環境（session あり） | BOUND | last_os / last_environment |
| その技術A（session なし） | UNRESOLVED | 推測しない |
| 前の技術（複数 Record） | UNRESOLVED | 一意でない |
| Windowsの方（複数 Windows） | UNRESOLVED | 一意でない |
| Pythonの方（複数 Python） | UNRESOLVED | 一意でない |
| 別の方法 | UNRESOLVED | 名前がない |

推測による Bind は 0。clarification として UNRESOLVED を残す。

## 5. Conflict / Unknown

混ぜたもの:

- 公式: Python 3.12 対応
- 第三者: Python 3.13 対応
- 別資料: 3.13 未対応

結果:

- Conflict は 2 件以上。winner = None
- 「では3.13で確実に動く？」→ answer=UNKNOWN。feasible / safe / correct は出さない
- Python 3.13 は UNKNOWN のまま。historical を current に昇格させない

## 6. Evidence / Source Isolation

A: Python 3.12 / Windows / CUDA 12.3  
B: Python 3.13 / Ubuntu / CUDA 12.4  
C: URSim / Docker  

「AをPython 3.13に変更」したあと:

- python_version = 3.13 / UNKNOWN / source=replacement_missing
- os は windows のまま（B の Linux を使わない）
- cuda は 12.3 のまま（B の 12.4 を使わない）
- ursim / C の docker は入らない
- copied_from_old = false

## 7. LLM 入力削減

P-12 の拡張。全記憶 100 Facet 超（実測 304）に対し、機械的選択後は 4。

重要なのは「LLM が賢く整理できた」ことではない。**LLM に整理させる必要がない状態まで機械的に絞れた**ことである。全記憶を LLM に渡す経路は作っていない。

## 8. Search 最小化

- 足りる → 検索 **0**（PASS）
- 一部不足 → 検索 **1**（python_version:3.13）
- 全面不足 → 検索 **2**（python_version:3.13 と cuda:12.4）。全件再検索フラグは立たない

## 9. Goal → Discovery → Coverage → Routing → Reuse → Decision Support

同一 experimental 呼び出しで連続して通した。責務は混ぜていない。

| 段階 | 今回の役割 | 実測 |
|------|------------|------|
| Goal | 何をしたいか | あり |
| Discovery | 何を知る必要があるか | invoked。feasible / safe / correct なし |
| Coverage | 何が分かっていて何が不足か | required: external_evidence / environment / python_version |
| Routing | どの Evidence を取り出すか | python_version |
| Reuse | 再利用可能か | **no_reuse**（後述の限界） |
| Decision Support | 判断材料を提示する | あり。判定そのものではない |

既定経路（JSON を読む Tool）は従来どおり `facet_discovery="off"`。

## 10. 実装までの接続

Experimental の独立 fixture（一時ディレクトリ）で:

要求 → 記憶済み ResearchRecord → Spec → Code → Test

まで通した。既存の重要な開発物は変更していない。`liba_demo_tool` は上書きしていない。live Research は使っていない。

## 11. Cursor / Local Agent の責務

**現段階では接続しない。** 第1回として分担は成立する、と判断した。

| Cursor | Local Agent |
|--------|-------------|
| 実際のコードベース操作 | Session |
| 編集 | ResearchRecord / 記憶 |
| 実行 | Requirement / Facet 管理 |
| テスト | 再利用、必要情報の選択 |
| 開発環境との直接接続 | ユーザーとの対話 |

Local Agent が切った Facet / Spec / 不足点を Cursor に渡し、Cursor がコードを触る、という形なら役割は重ならない。今それを実装すると、責務が混ざる。

---

## 12. 第1回総合判定

### できること

- session id があれば正しい ResearchRecord に bind できる
- 記憶が増えても、LLM へ渡す Facet 数は増えない（100 Record でも 4）
- 変わった Facet だけ再調査し、残りを保持できる
- historical Evidence を新しい Version にコピーしない
- 一意でない参照は UNRESOLVED のまま残せる
- Conflict を 1 つの正解に潰さない
- 別技術・別環境の Evidence を流用しない
- 足りるときは検索 0 にできる
- fixture なら Spec → Code → Test まで通せる

### できないこと

- Production の既定 Workflow には未接続
- live Web Research は今回測っていない
- `standard_workflow` の Reuse は session bind を使わず、通しテストでは `no_reuse` になった（Phase O の壁と一致）
- Cursor との実接続は未実装
- 曖昧参照を推測で解決しない（これは禁止事項なので、できないことは正しい）
- Unknown を Confirmed へ勝手に変えない（これも正しい）

### 機械的処理で成立したこと

bind / diff / select、Version 隔離、Facet 保持、historical 化、LLM 入力削減、検索最小化。

### LLM が必要なこと

機械的に切り出せない解釈、判断材料の文章化、Spec の説明、実装方針の下書き。記憶の整理そのものには LLM を使わない。

### Research の限界

今回の Research は fixture。live の公式資料 / 第三者資料を取りに行く経路は、第1回の実測対象にしていない。Conflict の保持はできるが、資料の真偽判定はしない。

### 記憶構造の限界

Facet は Record 単位。Graph も Vector もない。横断検索は「同じ facet_id が複数 Record にある」ことしか見ていない。一意でなければ止める。これは限界であり、同時に安全側である。

### Session の限界

Session は `last_research_id` と現在 Facet を持つ。standard_workflow の Reuse にはまだ繋がっていない。「その技術A」は Adapter では bind できるが、通し Workflow の Reuse は no_reuse のまま、というずれが残る。

### Version 管理の限界

置換は正規表現と session の現在値に依存する。「だけ変える」意図が文面に無いと、取りこぼす可能性がある。複数 Version の並行（3.12 用と 3.13 用を同時に current にする）は持っていない。current は 1 値、残りは historical。

### 曖昧要求の限界

一意でない参照はすべて UNRESOLVED。ユーザーへの聞き返し文面は、今回 LLM に書かせていない。clarification は状態として残すところまで。

### 実装 Workflow への接続可否

Experimental fixture では可。Production Tool や既存の重要コードへの接続は不可（今回やっていないし、やるべきでもない）。

### Cursor との役割分担

文書上は成立する。実装は第1回の対象外。

### 現時点で作るべきもの

- Experimental Adapter の維持（pointer / session / memory_slice）
- 同じ経路の再測（live Research を足すのは次）

### 現時点で作らないもの

- Reasoning Core / Graph Core / RAG / Vector DB / Knowledge Base
- 全記憶を LLM に渡す整理層
- Discovery による safe / feasible / correct
- 新規 C3
- Cursor 接続の本番実装
- Production への既定接続

### Production へ進める条件

1. 既定 `facet_discovery="off"` を維持したまま、experimental だけ再現できる
2. session bind が Reuse / Routing と矛盾しない（今は Reuse が no_reuse）
3. live Research でも混入 0・slice 数が増えないことを再測する
4. Phase F / O / P / P-7 が落ちない
5. Unknown / Conflict を正解に潰す経路が無い

今は **REJECT_NOW**（Core 化しない、Production に載せない）。

### 次の Phase で検証すべきもの

- session bind を Reuse に experimental 接続する（既定は off のまま）
- live Research での混入 0 の再測
- clarification 文面を、UNRESOLVED から機械的テンプレートで出すか
- Cursor へ渡す最小手渡し（Spec / 不足 Facet / 触ってよい範囲）の設計だけ。実装は急がない

---

## ラベル

```text
RECORD       : 5〜100 件の fixture、Version 履歴
EXPERIMENTAL : pointer / session / memory_slice / R1 harness
PARTIAL_PASS : 第1回総合（機械的経路は成立、Production 未接続）
PASS         : 項目 1〜11 の experimental 実測
REJECT       : 新 Core、全記憶を LLM に渡す整理層
REJECT_NOW   : memory_slice の Core 化、Production 接続
```

Phase F ADOPT、既定 `facet_discovery="off"`、C3=0 は維持。
