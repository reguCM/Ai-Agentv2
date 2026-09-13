# Phase P：ResearchRecord → Development Session 引き継ぎ

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_185728_phase_p_session_handoff`  
**Production 変更:** 0  
**新規 C3:** 0  
**`standard_workflow` 既定値:** `facet_discovery="off"`（未変更）  
**判定:** `PARTIAL_PASS`

## 目的

新しい Reasoning Core / Graph / RAG / Knowledge Base は作らない。

Phase O で残った壁を、既存 TDA 経路の上に **小さな Experimental Adapter** だけ足して測る。

| 壁 | Phase O の実測 | Phase P で試したこと |
|----|----------------|----------------------|
| B | 「その技術A」が ResearchRecord に結び付かない | session の `last_research_id` で bind。文字列一致だけでは bind しない |
| E | 「3.12ではなく3.13」が first-match で 3.12 のまま | 置換を読み、3.12 を historical、3.13 を UNKNOWN。Evidence はコピーしない |
| F | 次の要求で Python / OS が Coverage から消える | session の Facet 一覧として保持する（Coverage 既定は変えない） |

## 追加したもの（Core ではない）

| もの | ラベル | 役割 |
|------|--------|------|
| `pointer_resolution` | EXPERIMENTAL | その技術A / 前のやつ / その環境 を session 識別情報で解決。無ければ UNRESOLVED |
| `development_session` | EXPERIMENTAL | Facet 保持、Version 履歴、Conflict 保持 |
| `python_version_delta` 拡張 | EXPERIMENTAL | 「3.12ではなく3.13で」「Pythonだけ3.13に変更」 |
| `patch_runtime_only` | EXPERIMENTAL | RUNTIME_PYTHON だけ変える。payload 関数は触らない |

`standard_workflow` の既定経路には接続していない。

---

## 1. 何ができたか

Adapter を使った同一 Session では、次が **できた**。

- 「その技術A」を `RR-A` に bind する（session id 必須。推測しない）
- Python 3.12 の Spec → Experimental Code → Test
- Windows / Docker / CUDA を足しても、前の Facet を session 上で残す
- Python だけ 3.13 に変えたとき、不足は Python 3.13。Windows / CUDA / License は再利用。全件再調査しない
- 3.13 の Evidence は UNKNOWN。3.12 は historical として残す。コピーしない
- Code の payload 関数を壊さず runtime 行だけ変える
- 「3.13ではなく3.12に戻して」で、履歴の 3.12 を confirmed に戻す
- 公式 3.12 と第三者 3.13 の Conflict を保持し、「確実に動く？」は UNKNOWN

既存 Workflow 単体では、「その技術A」の bind は **できなかった**（as-is 0.00）。

## 2. 何ができなかったか

- 既定 Workflow に pointer bind / Facet 保持を入れていない（意図どおり）
- Coverage の Required 一覧そのものは、Phase O と同じく次手番で落ちる。保持は session Adapter 側
- Spec は bound 候補の environment を丸ごと含む（CUDA / GPU まで）。必要部分だけの切り出しではない
- live Web / 実 LibA は使っていない（fixture RECORD）
- Discovery に feasible を足さなかったので、「確実に動く？」の答えは Adapter の UNKNOWN である

## 3. どこが壁だったか

壁 B / E / F は **Adapter で橋渡しできたことが確認できた**。既定経路ではまだ壁のまま。

壁 G（URSim 推測）と壁 H（Discovery が判定を始める）は、今回も発生していない。

## 4. 何を再利用できたか

P-4「Pythonだけ3.13に変更したので確認して」:

- 不足: `python_version:3.13`（UNKNOWN）
- 再利用: license Y、os Windows、CUDA 12.3
- Docker は ResearchRecord に無いので UNKNOWN のまま保持（確認済みにはしない）
- `full_reresearch`: false、`searches_estimate`: 1

## 5. 何を再調査したか

live Web Search は 0（tda なし）。

再調査 **対象** として印を付けたのは Python 3.13 だけ。3.12 の Evidence を 3.13 の答えにしていない。

## 6. 次に何を試すべきか

- pointer bind を experimental 経路だけに接続する（既定は off）
- Coverage が session Facet を Candidate として残す（Required にしない）
- Spec を session Facet だけで組み立て、候補 environment の丸ごとコピーをやめる

作らないもの: Reasoning Core、Graph、RAG、Knowledge Base、3.12→3.13 の Evidence コピー、Discovery への feasible。

---

## 参照表現

| 表現 | session あり | session なし |
|------|--------------|--------------|
| その技術A | BOUND（`RR-A`） | UNRESOLVED（推測しない） |
| 前の技術A | BOUND | UNRESOLVED |
| 3.12ではなく3.13 | VERSION_REPLACE（3.13 を選択。3.12 は historical） | 同じ（文面だけで読める） |
| その環境 | BOUND（last_os = windows） | UNRESOLVED |
| 前のやつ | BOUND（last_research_id） | UNRESOLVED |

文字列一致だけで技術を当てない。id が無いときは UNRESOLVED。

---

## 評価指標

| 指標 | 値 |
|------|-----|
| ResearchRecord binding accuracy（Adapter） | 1.00 |
| 既存 resolve の binding | 0.00 |
| Version replacement accuracy | 1.00 |
| Facet retention | 1.00 |
| Changed-facet isolation | 1.00 |
| Unknown preservation | 1.00 |
| Conflict preservation | 1.00 |
| Unnecessary research suppression | 1.00 |
| Spec → Code | 1.00 |
| Code → Test | 1.00 |
| Test → 再評価（3.12 へ戻す） | 1.00 |

最終 Facet（P-5 のあと）:

- python_version = 3.12（confirmed, historical_restore）
- os = windows（confirmed）
- cuda = 12.3（confirmed）
- license = Y（confirmed）
- docker = docker（UNKNOWN。Research に無かった）

## 連続セッションで引き継いだもの

Goal / Gate / Discovery / Coverage / Routing は各手番で Workflow が出す。  
ResearchRecord・session Facet・Spec・Code・Test・Version 変更履歴は Development Session が持つ。

Coverage の Required 一覧は手番ごとに作り直される。session Facet は消えない。この差が壁 F の本体である。

## ラベル

```text
RECORD        : fixture RR-A、Version 履歴、Conflict
EXPERIMENTAL  : pointer / session / version delta / runtime patch
REJECT        : 新 Core、3.12 Evidence の 3.13 コピー、確実に動く？への feasible
```

Phase F ADOPT（c3=0）、Phase O 連続テスト、Skip Policy / Coverage / Routing の既存テストは維持。
