# 環境調査の既知失敗

unittest ではない。自己修復の分岐仕様でもない。

## research_misses_request

ケース: `cases/insufficient_research_memory_capacity.json`

要求は「メモリ使用率」。research は `Win32_PhysicalMemory` の Capacity 合計を実環境で取れて high になった。

- Verifier は「コマンドが実行できた」だけを見る
- 要求を満たすかは見ていない
- 実装は届いた（`code_received`）。失敗は受け取りではなく、調査結果の意味

次の実験: この不十分さを LLM が判断し、research に戻れるか。
正解コマンドはケースにも CONTRACT にも書かない。

## 再調査実験（qwen3_8b / temperature=0 / 3回）

`max_research_rounds: 2`。3回とも同一。

1. research → `wmic os get Caption,OSArchitecture,Version`（OS情報）
2. judge: 要求を満たさない → missing `メモリ使用率の取得方法`
3. research again → `Win32_OperatingSystem.TotalVisibleMemorySize`（総物理メモリ）
4. judge: まだ使用率ではない → missing `メモリ使用率（使用中の割合）を取得する方法`
5. 上限到達。usable_findings は空。実装は未実装（`llm_marked_unimplemented`）

分かったこと:

- LLM は research に戻れた
- 不十分な結果を実装しなかった
- 2回目で使用率そのものまでは届かなかった

## judge_verify_failed_retry

ケース: `cases/judge_verify_failed_retry.json`

④ `research_implement` を止めて保存した実測。Verifier は候補を `-Command` 付きで実行した。`TotalPhysicalMemory` が無く 0 除算。`usable_findings` は空。Judge は `no_json` で `missing` が無く、`research_no_next_question` で止まった。

孤立テストでは JSON と missing は返せる。次は missing の質（A/B/C）。エラー文のコピーは C。正解コマンドは書かない。

```text
python -m research.llm_benchmarks.judge_verify_retry
```

正解コマンドはケースにも CONTRACT にも書かない。
