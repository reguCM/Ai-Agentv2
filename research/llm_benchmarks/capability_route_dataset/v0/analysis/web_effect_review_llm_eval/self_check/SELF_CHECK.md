# SELF_CHECK — 評価器自己検証

- 生成時刻: `2026-08-24T04:10:16.610908+00:00`
- モデル: `qwen3:8b`
- 原評価ファイルは削除・上書きしていない

## 本文なしケース一覧（全ヒット empty）

| case_id | 原Q1 | 再Q1 | violation候補 | Q1変更 |
|---------|------|------|---------------|--------|
| B05 | ○ 有用 | ？ 本文なし等で判断不能 | True | True |
| C03 | ◎ 十分に有用 | × ほぼ無用 | True | True |
| A06 | × ほぼ無用 | × ほぼ無用 | False | False |

## 全ケース 元評価 → 再評価

### B05

- 質問: Pythonのリストとタプルの違いを簡単に説明して
- has_content=0 / empty=3 / all_empty=True
- q1_rule_violation_candidate: **True**
- q1_changed: **True**
- recheck_reason: 原評価は全本文なしなのにQ1=◎/○（ルール違反候補）。独立Q1再評価で修正；Q1: '○ 有用' → '？ 本文なし等で判断不能'

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | False |
| Q1 | ○ 有用 | ？ 本文なし等で判断不能 |
| Q2 | △ ほぼ変化なし | ◎ 明確に改善 |
| Q5 | WEBなし | WEBあり |

- 原Q1理由: Webなし回答と内容がほぼ一致し、必要情報は網羅しているが若干簡潔
- 再Q1理由: 全検索結果が本文なし

### C02

- 質問: Ollamaについて詳しく教えて
- has_content=1 / empty=2 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **False**
- recheck_reason: 独立再評価実施（Q1変更なし）

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | True |
| Q1 | ◎ 十分に有用 | ◎ 十分に有用 |
| Q2 | ◎ 明確に改善 | ◎ 明確に改善 |
| Q5 | WEBあり | WEBあり |

- 原Q1理由: Webあり回答が検索結果から開発者情報やCLI/GUIなどの詳細を追加し、情報量が大幅に増加
- 再Q1理由: 検索結果1がOllamaの開発者・機能等を具体的に説明

### C03

- 質問: RTX 3060って今どういう扱いですか？
- has_content=0 / empty=5 / all_empty=True
- q1_rule_violation_candidate: **True**
- q1_changed: **True**
- recheck_reason: 原評価は全本文なしなのにQ1=◎/○（ルール違反候補）。独立Q1再評価で修正；Q1: '◎ 十分に有用' → '× ほぼ無用'

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | False |
| Q1 | ◎ 十分に有用 | × ほぼ無用 |
| Q2 | △ ほぼ変化なし | △ ほぼ変化なし |
| Q5 | WEBなし | WEBなし |

- 原Q1理由: 回答はRTX 3060の基本スペックと市場状況を説明しており、質問への直接的な回答を提供
- 再Q1理由: 全検索結果が本文なし

### A04

- 質問: 今のNVIDIAの株価の雰囲気を教えて
- has_content=3 / empty=2 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **True**
- recheck_reason: Q1: '○ 有用' → '× ほぼ無用'

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | False |
| Q1 | ○ 有用 | × ほぼ無用 |
| Q2 | ◎ 明確に改善 | ◎ 明確に改善 |
| Q5 | WEBあり | WEBあり |

- 原Q1理由: Webなし回答はAI分野の成長を背景に株価が上昇していると述べているが、具体的な数値や最新情報は含まれていない
- 再Q1理由: 検索結果が株価や市場の雰囲気に関する具体的情報を含んでいない

### A06

- 質問: Python 3.13で追加された主な変更点を教えて
- has_content=0 / empty=1 / all_empty=True
- q1_rule_violation_candidate: **False**
- q1_changed: **False**
- recheck_reason: 独立再評価実施（Q1変更なし）

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | False |
| Q1 | × ほぼ無用 | × ほぼ無用 |
| Q2 | △ ほぼ変化なし | × 劣化 |
| Q5 | WEBなし | WEBなし |

- 原Q1理由: 検索結果がPython 3.0に関する情報で、質問のPython 3.13とは無関係
- 再Q1理由: 本文なし

### C05

- 質問: この手のエージェントって今どこまで実用的なの
- has_content=4 / empty=1 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **True**
- recheck_reason: Q1: '◎ 十分に有用' → '○ 有用'

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | True |
| Q1 | ◎ 十分に有用 | ○ 有用 |
| Q2 | ◎ 明確に改善 | ◎ 明確に改善 |
| Q5 | WEBあり | WEBあり |

- 原Q1理由: Webあり回答が検索結果の具体例（RPA、Rational Agentなど）を活用して詳細な実用例を提示
- 再Q1理由: 検索結果3が実用例を含むため

### WB01

- 質問: Gitとは何かを初心者向けに説明して
- has_content=3 / empty=2 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **False**
- recheck_reason: 独立再評価実施（Q1変更なし）

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | False |
| Q1 | × ほぼ無用 | × ほぼ無用 |
| Q2 | △ ほぼ変化なし | × 劣化 |
| Q5 | WEBなし | WEBなし |

- 原Q1理由: 検索結果の本文が全て空または不適切で、有用な情報が得られなかった
- 再Q1理由: 検索結果の本文が不完全または関連性がない

### WB02

- 質問: Dockerコンテナの基本的な考え方を教えて
- has_content=5 / empty=0 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **False**
- recheck_reason: 独立再評価実施（Q1変更なし）

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | True |
| Q1 | ◎ 十分に有用 | ◎ 十分に有用 |
| Q2 | ◎ 明確に改善 | × 劣化 |
| Q5 | WEBあり | WEBなし |

- 原Q1理由: Webあり回答が検索結果のDocker Engineやリリース年などの具体的な情報を含むため
- 再Q1理由: 検索結果1がDockerコンテナの基本的な考え方を直接説明

### WB04

- 質問: JSONとは何か、何に使うかを教えて
- has_content=5 / empty=0 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **False**
- recheck_reason: 独立再評価実施（Q1変更なし）

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | True |
| Q1 | ◎ 十分に有用 | ◎ 十分に有用 |
| Q2 | ○ 改善 | ◎ 明確に改善 |
| Q5 | WEBなし | WEBあり |

- 原Q1理由: Webなし回答がJSONの定義・用途・特徴を網羅的に説明
- 再Q1理由: 検索結果1がJSONの定義と用途を具体的に説明している

### WB07

- 質問: CUDAとは何かを説明して
- has_content=4 / empty=1 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **True**
- recheck_reason: Q1: '◎ 十分に有用' → '○ 有用'

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | True |
| Q1 | ◎ 十分に有用 | ○ 有用 |
| Q2 | ○ 改善 | ○ 改善 |
| Q5 | WEBあり | WEBなし |

- 原Q1理由: Webなし回答がすでにCUDAの定義と用途を十分に説明している
- 再Q1理由: 検索結果2にCUDAの定義が含まれている

### WB12

- 質問: Linuxとは何かを概要で教えて
- has_content=4 / empty=1 / all_empty=False
- q1_rule_violation_candidate: **False**
- q1_changed: **False**
- recheck_reason: 独立再評価実施（Q1変更なし）

| 項目 | 元評価 | 再評価 |
|------|--------|--------|
| usable_evidence | — | True |
| Q1 | ◎ 十分に有用 | ◎ 十分に有用 |
| Q2 | ◎ 明確に改善 | ◎ 明確に改善 |
| Q5 | WEBあり | WEBなし |

- 原Q1理由: Webあり回答がカーネルの特性やディストリビューションの詳細を追加し、説明がより具体的になった
- 再Q1理由: 検索結果1・2・4にLinuxの定義や関連概念が含まれており、質問への回答に十分な情報が得られる
