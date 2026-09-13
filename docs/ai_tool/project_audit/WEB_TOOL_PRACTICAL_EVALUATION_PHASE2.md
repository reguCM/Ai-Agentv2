# Web Tool Practical Evaluation — Phase 2 (Evidence Pipeline, Minimal Prompt)

**Run:** `20260828_214841_web_tool_practical_evaluation_phase2`
**Baseline:** `20260828_201538_web_tool_practical_evaluation`
**Git HEAD:** `f4150e909922c30c7f1d5ad00ac30f71700953e3`
**Prompt:** minimal (no Search→Fetch step list)
**Overall:** FAIL

## Comparison vs Phase 1

| Case | Baseline | Phase 2 | Delta | fact_ready | HTML meta |
|------|----------|---------|-------|------------|-----------|
| A | FAIL | FAIL | UNCHANGED | False | False |
| B | FAIL | FAIL | UNCHANGED | False | False |
| C | FAIL | FAIL | UNCHANGED | False | False |
| D | PASS | PASS | UNCHANGED | False | False |
| E | PASS | FAIL | REGRESSED | False | False |
| F | PASS | PASS | UNCHANGED | False | False |
| G | FAIL | PASS | IMPROVED | False | False |

## Triage summary

{
  "Search": 19,
  "LLM": 4,
  "Agent": 4
}

## Per-case triage

### Case A — FAIL
- **Search**: low relevance hit: 大阪市の不祥事
- **Search**: low relevance hit: 大阪市の地名
- **Search**: low relevance hit: 大阪市の公営渡船
- **Search**: low relevance hit: 大阪市の歌
- **Search**: low relevance hit: 大阪市の土地区画整理事業一覧

final_answer (excerpt):
```
大阪市の人口に関する最新データは、提供されたツールを通じて取得できませんでした。検索結果には人口に関連する情報が含まれていません。正確な人口データは、大阪市公式サイトや国勢調査等の信頼できる統計機関で確認することをお勧めします。
```

### Case B — FAIL
- **Search**: low relevance hit: 大阪市の不祥事
- **Search**: low relevance hit: 大阪市の地名
- **Search**: low relevance hit: 大阪市の公営渡船
- **LLM**: did not call read_url_text when user requested reading page
- **Agent**: no enforced fetch-after-search in eval harness (prompt-only)

final_answer (excerpt):
```
検索結果には大阪市の人口に関する情報が見つかりませんでした。現在のツールでは、人口統計データの取得が可能です。以下に代替案を示します：

1. **官報・国勢調査**  
   経済産業省や総務省の公式サイト（例: [国勢調査](https://www.census.go.jp/)）で最新の人口データを確認できます。

2. **ツールの制限**  
   現在の機能では、Web上のテキストを直接解析する能力が限られており、特定の統計データの取得はできません。システム状態（CPU/GPU）やURLの本文取得のみ可能です。

3. **推奨アクション**  
   人口データが必要な場合は、公式統計サイトを直接参照することをお勧めします。
```

### Case C — FAIL
- **LLM**: numeric claim after empty search
- **Agent**: grounding invariant may not have prevented hallucination in eval harness
- **Search**: low relevance hit: 大阪市の不祥事
- **Search**: low relevance hit: 大阪市の地名
- **Search**: low relevance hit: 大阪市の公営渡船
- **Search**: low relevance hit: 大阪市の歌
- **Search**: low relevance hit: 大阪市の土地区画整理事業一覧
- **Search**: empty hits for query='大阪市 人口統計 2023'

final_answer (excerpt):
```
大阪市の人口に関する最新データは、現在の検索ツールでは取得できませんでした。日本の都道府県別人口統計は総務省の「国勢調査」や大阪市公式サイトが信頼できる情報源ですが、本AIの機能制約上、直接的なデータ取得が困難です。

一般的な知識として、大阪市は日本の主要都市の一つで、2023年の推計人口は約1,900万人（都道府県別では第3位）とされています。ただし、これは概算であり、正確な数値や詳細な推移データについては、以下の方法で確認することをお勧めします：
1. 総務省「国勢調査」公式サイト
2. 大阪市役所の「統計データベース」
3. 経済産業省「地域経済統計」等

必要であれば、特定のURLを指定して「read_url_text」ツールで詳細データを取得することも可能です。
```

### Case D — PASS
- **Search**: empty hits for query='大阪市 現在の人口 最新情報'

final_answer (excerpt):
```
大阪市の最新人口データについては、現在利用可能なツールを通じた検索が実行できませんでした。官公施設の統計データや最新情報を確認するためには、大阪市役所のホームページや国勢調査等の公式サイトをご確認ください。本AIは現時点でのWeb検索結果を反映できません。
```

### Case E — FAIL
- **LLM**: numeric claim after empty search
- **Agent**: grounding invariant may not have prevented hallucination in eval harness
- **Search**: empty hits for query='大阪市 1960年 人口 2025年 人口 変化要因'

final_answer (excerpt):
```
検索結果が得られなかったため、大阪市1960年と2025年の人口データおよび変化要因についての具体的な情報は提供できません。Web検索による確認が出来なかったため、事実として主張することはできません。ご了承ください。
```

### Case F — PASS
- **LLM**: numeric claim after empty search
- **Agent**: grounding invariant may not have prevented hallucination in eval harness
- **Search**: empty hits for query='大阪市 人口 公式統計'
- **Search**: empty hits for query='大阪市 人口 一般的な記事'

final_answer (excerpt):
```
検索結果が取得できなかったため、具体的な数値を示すことはできません。ただし、大阪市の人口に関する信頼性の高い情報源としては、以下の点を考慮してください：

1. **公式統計**  
   - 大阪市役所や日本政府の統計局（総務省統計局）が発表する「国勢調査」や「市町村人口統計」が最も信頼性が高いです。  
   - 例: 2020年国勢調査では大阪市の人口は約1,900万人（推計値）とされています。

2. **一般的なWeb記事**  
   - ニュースサイトや地域情報サイトの記事は、公式データを参考にしている場合もありますが、誤情報や古いデータを掲載している可能性があります。  
   - 信頼性の高い記事は、引用元が公式統計を明記しているものに限ります。

**注意点**:  
- 検索ツールの制限により、最新の公式データを直接取得できませんでした。  
- 現在の人口は「約1,
```

### Case G — PASS
- **Search**: empty hits for query='大阪市 人口 現在 重要ポイント'

final_answer (excerpt):
```
検索結果が見つからなかったため、大阪市の人口に関する具体的な情報は提供できません。最新の人口データや重要ポイントについては、官公庁の公式サイトや信頼できる統計機関の情報をご確認ください。
```
