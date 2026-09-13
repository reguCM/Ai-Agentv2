# TDA Facet Discovery 取りこぼし改善（Phase N+2）

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_181956_discovery_coverage`  
**Production 変更:** 0  
**新規 C3:** 0  
**Standard Workflow 変更:** なし（デフォルトも未変更）  
**判定:** `GENERALIZED_PASS`（Core は不要。Workflow へは未接続）

`Facet Discovery`（要求から、判断に必要な情報項目を見つける処理）の Relevant Recall は Skip Policy 評価で **0.80** だった。穴は主に Cue 表に無い言い換え（例: 「使えるAPIを調べて」）だった。

今回の目的は Discovery を賢くすることではなく、

> 必要な Facet を見落とさないために、既存構造のどこを足せばよいか

を測ること。

```bash
python ai_tool/run_tda_discovery_coverage_evaluation.py
pytest tests/ai_tool/project_audit/test_discovery_coverage.py -q
```

---

## 1. 何が見つかったか

取りこぼしは5種に分かれた。

| 種類 | 例 | Keyword-only (K) |
|------|----|------------------|
| 言い換え | 確認して / 動く？ / 使えるAPI | ほぼ全部落ちる |
| 暗黙条件 | 人間が途中で操作できる？ | Cue があると **確定しすぎる**（over-promotion） |
| 条件変更 | Python 3.12なら | K でも数字があれば拾える |
| 比較 | AとBどちらがいい | 比較 が無いと軸が無い |
| Follow-up | その環境なら | 参照が無いと推測しがち／Cue が無いと何も出ない |

**Alias だけでは 0.80 を超えない**（KA = 0.79）。目的・条件スロット（GC）を足して初めて 1.00。複雑化そのものが理由ではなく、**「何を確認したいか」を表に出すこと**が必要だった。

Required / Candidate / Unknown を分けないと、UR Research があるだけで Control Authority を「必須」にしてしまう。結論（操作できる）は出していないが、**必要性の断定**は既に行き過ぎ。

---

## 2. 何が改善したか

4方式（いずれも LLM 推論なし）:

| 方式 | Required Recall | False Discovery | Suppression |
|------|-----------------|-----------------|-------------|
| K keyword（現行 `discover_facets`） | **0.29** | 0 | 1.00 |
| KA keyword + alias | **0.79** | 0 | 1.00 |
| GC goal + context（スロット） | **1.00** | 0 | 1.00 |
| GCR GC + 既存 Research | **1.00** | 0 | 1.00 |

Skip Policy 時の 0.80 を下回らない条件は **GC 以上**で満たす。GCR の追加価値は Recall ではなく、

* 変更 Facet だけを required にする
* 既存 CUDA / License を candidate / keep に残す
* UR があるときだけ Control Authority を candidate にする
* 無いときは unknown（発明しない）

実装: `ai_tool/experimental/development_assistance/facet_coverage.py`  
現行 `facet_discovery._CUES` は **未変更**（K を測るため）。

JSON コード生成は Skip。License / Docker / CUDA を付けない。

---

## 3. 何がまだ見落とされるか

このセットでは GCR の required_recall は 1.00 だが、**未登録の言い換えはまた落ちる**。Alias 表は Cue 表と同じ種類のドメイン知識である。

実測で残った粗い点:

* CUDA 12.3 の follow-up で、数字正規表現が `version` を余分に required にする（Docker 等の洪水ではない）
* 「これで動く？」は対象が空。environment は出すが Target は推測しない
* 未知の装置名に対する暗黙 Facet は unknown のまま（正しい取りこぼし）

---

## 4. 何を作らなかったか

```text
Reasoning Core     REJECT
Graph / KG         REJECT
RAG / Vector DB    REJECT
LLM 推論で Facet 発明  REJECT
safe / feasible 判定   REJECT（Discovery 禁止のまま）
```

候補と確定の3分類は Experimental envelope であり、新しい Core ではない。

---

## 5. Production に何を変更しなかったか

```text
Production changes = 0
New C3 Core = 0
standard_workflow default = 変更なし
discover_facets Cue 表 = 変更なし
```

---

## 6. 次に何をすべきか

1. Skip Policy（Policy D）と coverage overlay（GC/GCR）を **Experimental workflow フラグ**で接続する案を、実装前に再判定する。デフォルトは off。
2. 効いた alias（API / 確認して / 動く？）を `discover_facets` へ **最小マージ**するかは別判定。Recall のためだけに Cue を膨らませない。
3. CUDA 数字と製品 Version のスロット分離（RECORD）。

---

## テストケース（必須）

### ケース1 連続 follow-up

PyTorch 調査 → Python 3.12 → CUDA 12.3 → Windows → RTX 3060 → Toolにできそう？

* 既存 Facet を保持（python_kept / cuda_kept）
* Python 変更で CUDA を書き換えない
* RTX から OS/License を推測しない
* 最後は `feasibility_check`。feasible / safe は出さない。Decision Support の領域

### ケース2 Partial Research

「前に調べたAについて、Python 3.12の場合だけもう少し調べて」  
Target = A、変更 = Python、CUDA / License は keep。full_reresearch = False。

### ケース3 その環境なら

参照なし → `UNRESOLVED`（Windows/Docker を選ばない）。  
session に last_environment あり → environment を required。

### ケース4 人間が途中で操作できる？

UR Research あり → control_authority は **candidate**。required に昇格しない。結論は出さない。  
一般 OSS store → unknown。

### ケース5 AとBどちらがいい？

比較軸（target / environment / version / license / conflict）を列挙。どちらを使うかの判定はしない。

---

## False Discovery

「PythonでJSONを読むコードを書いて」「JSONとは何ですか？」で GCR は Skip。forbidden Facet 0。

K の over-promotion 1件: UR Cue が「人間が」で Control Authority を required にしてしまう。GC で candidate に下げた。

---

## Unknown / Conflict / Version

* Python 3.13 は missing。CUDA から推論しない
* 公式 3.12 / 第三者 3.13 の Conflict はレコード上保持
* A 5.15 に 5.17 を適用する判定は出さない

---

## REUSE / RECORD / DEFER / EXPERIMENTAL / REJECT

| 項目 | 判定 |
|------|------|
| `discover_facets` / Routing / ResearchStore / Goal Abstraction | REUSE |
| Alias 表 + スロット抽出 | EXPERIMENTAL |
| Required / Candidate / Unknown | EXPERIMENTAL |
| Alias を本番 Cue へマージ | RECORD |
| 製品 Version と CUDA 数字の分離 | RECORD |
| Reasoning / Graph / RAG | REJECT |
| Discovery が feasible を出す | REJECT |

---

## 判定の読み方

`GENERALIZED_PASS` は「測った取りこぼしを埋めるのに Core は不要」という意味。  
**Standard Workflow のデフォルトに入れる、という意味ではない。** Cue/alias はまだ表であり、未知の言い換えは落ちる。接続は Skip Policy の `ADOPT_CONDITIONAL` とセットで次 Phase。
