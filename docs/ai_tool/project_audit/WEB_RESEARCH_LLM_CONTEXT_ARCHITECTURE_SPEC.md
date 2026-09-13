# Web Research / LLM Context Architecture — Specification

**Version:** 1.0  
**Date:** 2026-08-29  
**Status:** ADOPTED (design philosophy — Production chain unchanged)  
**Git HEAD at adoption:** `f881ae8`  
**Related:** [DEFENSIVE_CORE_DISCOVERY_POLICY.md](./DEFENSIVE_CORE_DISCOVERY_POLICY.md), [WEB_EVIDENCE_LIVE_LLM_CONTEXT_SHOOTOUT.md](./WEB_EVIDENCE_LIVE_LLM_CONTEXT_SHOOTOUT.md)

---

## 1. 基本思想

本システムは「Web情報を機械的に回答する検索システム」ではなく、

**LLMを主体とした会話型Agentが、必要に応じてWebを外部情報源として利用するシステム**

とする。

LLMの主な役割は以下とする。

* ユーザーの質問・意図の理解
* 必要性に応じたWeb利用の判断
* 検索方針・検索条件の決定
* Webから得た情報の文脈理解
* 複数情報の整理
* ユーザーとの会話
* 最終的な自然言語による回答

Web ToolはLLMを置き換えるものではなく、LLMの情報取得能力を拡張するものとする。

---

## 2. Web情報の扱い

Webから取得した情報について、システムが原則として「真偽を完全に判定してからLLMへ渡す」構造にはしない。

代わりに、LLMが判断するための材料として以下を可能な範囲で保持する。

* URL
* Webページ
* Source type
* ドメイン
* タイトル
* 公開日時・更新日時（取得可能な場合）
* 取得日時
* 抽出本文
* Evidence
* Web取得状態
* その他、信頼性判断に利用できるメタ情報

「公式」「政府」「自治体」「Wikipedia」「ニュース」「個人サイト」等のSource Typeは、絶対的な真偽判定ではなく、LLMの情報源選択・回答方針を補助する情報として扱う。

---

## 3. LLMの位置付け

LLMを最終的な会話の中心とする。

通常のケースでは、LLMがWeb Evidenceを利用して自然な回答を生成する。

Web情報を取得したこと自体を理由に、回答を機械的Factだけへ置き換えない。

例えば、

> 「大阪市の人口は約○○万人です。」

という自然な回答を基本とし、必要に応じて出典を提示する。

---

## 4. Mechanical Capability

Mechanical Verification / Mechanical Factは、LLMの代替回答機構ではなく、**独立した回答・検証能力として保有する**。

### 原則

* Mechanical AnswerによるLLM回答の常時置換は行わない。
* Productionへの自動接続は別途判断する。
* 機械的に確定可能な数値・年・Entity等は、独立したFactとして保持できる構造を維持する。
* LLMの回答とMechanical Factが異なる場合でも、即座にどちらかを破棄しない。
* 必要に応じてWarning、補足、再検索、Human Review等へ発展可能なCapabilityとして保持する。

つまり、

**Mechanical Verification ≠ Mechanical Answer**

とする。

---

## 5. 回答の優先順位

通常はLLMによる会話を優先する。

Mechanical FactはLLMを置き換えるのではなく、以下の用途に利用可能とする。

1. LLM回答の補助
2. 数値・年等の確認
3. 回答生成時の参考情報
4. 異常検出
5. 回答候補の比較
6. 将来のWarning / Retry等への発展
7. 必要に応じたユーザーへの直接提示

---

## 6. 複数回答

複数回答を常時提示する設計にはしない。

通常はLLMがユーザーに対して最も自然と判断した回答を1つ提示する。

ただし、LLMが以下のような状態と判断した場合には、複数情報・複数候補を提示してよい。

* 質問の解釈が複数存在する
* Web情報源によって値が異なる
* 年・定義・対象範囲が異なる
* 信頼できる情報源同士で矛盾がある
* 一つの回答に決めることがユーザー意図を損なう
* 不確実性を明示した方が適切

この場合も、目的は「機械的に複数の正解を並べる」ことではなく、**会話としてユーザーに判断材料を提示すること**とする。

---

## 7. Source / Evidenceの可視性

可能な範囲で、回答の根拠となったWebページをユーザーが辿れる設計を維持する。

ユーザーが必要とする場合、

* どのページを参照したか
* どの情報を根拠としたか
* 情報源の種類
* 複数情報源間の違い

を確認できるようにする。

システムは「自分が正解を保証した」とするのではなく、**ユーザーが根拠を確認できる透明性**を重視する。

---

## 8. Web情報の信頼性について

「Web情報をLLMが完全に吟味して真偽判定する」という方向には原則として進めない。

優先するのは、

**Source Selection → Evidence取得 → LLMによる文脈理解**

である。

ただし、明らかな取得失敗・Evidence不在・数値不一致等を機械的に検出できる防御機構は保持してよい。

---

## 9. 現行Architectureとの関係

現在のProduction chainを維持する。

```text
User
 ↓
LLM
 ↓
Search Strategy
 ↓
Search
 ↓
Fetch
 ↓
Extraction
 ↓
Evidence
 ↓
LLM
 ↓
Conversational Answer
```

Defensive Coreは必要に応じて以下を補助する。

```text
Web Status
Boundary
Mechanical Verification
Failure Diagnosis
Source / Evidence Metadata
```

これらはLLMを置き換えるのではなく、LLMによるWeb利用を安全・柔軟にするための補助能力とする。

---

## 10. Core Capabilityに対する追加評価基準

今後Core候補を評価する際には、従来の

* 現在必要か
* 将来価値があるか
* 再利用性
* コスト
* リスク

に加えて、

**「LLMの能力を置き換えるものか、LLMの能力を拡張するものか」**

を評価する。

### LLM拡張（優先検討）

* LLMの判断材料を増やす能力
* 情報源を選択する能力
* Evidenceを保持・追跡する能力
* 回答の出所を辿れる能力
* LLMの異常を検出する能力
* 複数の解釈を扱える能力
* 将来の回答方式変更を妨げない能力

### LLM置換（慎重）

LLMの仕事を機械的処理へ置き換えるだけのCapabilityは、実測上の必要性が確認されるまでProduction接続を急がない。

Policy module: `ai_tool/defensive_core_discovery_policy.py` → `llm_capability_role_criteria()`

---

## 11. Mechanical Verificationの現在の扱い

既存の `ai_tool/experimental/mechanical_verification/` は維持する。

| 項目 | 状態 |
|------|------|
| 分類 | **Experimental / Observation-oriented Capability (C3)** |
| Production Answer replacement | ❌ 行わない |
| Production Warning | 未接続 |
| Retry / Fallback | 未接続 |
| Claim Verification | 将来利用可能 |
| Mechanical Fact | 将来利用可能 |
| Source/Evidence provenance | 将来拡張可能 |

既存の実験結果・検証コードを破棄せず、将来の必要性が確認された際に利用できる状態を維持する。

---

## 12. 仕様変更の判断

今回の変更は、既存Production chainを変更するものではない。

変更するのは主として**設計思想・Capabilityの位置付け**である。

従って、既存Productionへの即時変更は不要。

今後の実装では、

**LLM中心の会話**
+
**Webによる情報取得**
+
**Evidence / Source transparency**
+
**Mechanical defensive capability**

を基本構造とする。

---

## 13. 自律開発へのルール

### 原則

「機械的にできるから機械化する」を目的にしない。

「LLMでは困難だが、機械化することでLLMの能力を補完できる」場合はCore候補として積極的に検討する。

### Production接続

以下のいずれかを確認するまで、Experimental CapabilityをProductionへ自動接続しない。

* 実測上の問題
* 明確なユーザー価値
* 十分なRegression
* Architecture上の必要性
* Human Review

### 予防能力

現在不要であっても、

* 低コスト
* 独立性が高い
* 複数用途が見込める
* Productionと衝突しない
* 将来削除可能

であれば、Experimental Coreとして先行保有することを認める。

ただし、Capabilityの乱立を防ぐため、既存のCore Discovery Policyの上限・Sunsetルールを維持する。

---

## 14. 最終的な設計思想

本システムは、

**「正解を一つに決めるAI」ではなく、
「LLMがユーザーとの会話を中心に、必要な情報・根拠・機械的Factを適切に利用できるAI」**

を目指す。

LLMが迷わない場合は、自然な一つの回答を返す。

LLMが迷う場合は、必要に応じて複数の解釈・情報源・回答候補を提示する。

機械的に確定できる情報は、LLMの代わりではなく、独立したFact / Verification能力として保持する。

Web情報については、完全な真偽判定をシステムの中心責務とせず、情報源・Evidence・取得状態を透明に保持し、LLMとユーザーが適切に判断できる材料を提供する。

**会話を主役とし、WebとMechanical Capabilityをそのための補助能力として利用する。**

---

## 15. 直近調査 Phase との整合

| Phase | 結論 | 本仕様との関係 |
|-------|------|----------------|
| Context Architecture Investigation (proxy) | RAW ≈ PASSAGE ≈ GROUPED；CLAIM-only 悪化 | Context 包装は LLM 拡張候補だが Production 不要 (C0) |
| Live LLM Shootout | D_HYBRID +1 case；Conflict 全形式成功 | LLM が source メタデータで会話的に区別可能 — 機械的 conflict resolver 不要 |
| Mechanical Verification | Observation-only；answer replacement なし | §4 / §11 と一致 |
| web_answer_boundary | Failure 時の numeric 抑制 | LLM 異常検出の defensive 例 (C4) |

**Context Format を Production へ接続しない**判断は、本仕様「LLM 中心・Web は拡張」と整合する。

---

## SCR-02

| 項目 | 内容 |
|------|------|
| ID | SCR-02 |
| Type | Design philosophy adoption |
| Production impact | NONE |
| Human Review | 不要（思想・評価基準のみ） |
| Document | 本ファイル |
