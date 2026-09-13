# Tool Result Contract v1

## 1. 目的

AI-Agent内で使用するTool Resultを、Agent本体、Chat UI、Runtime State、Failure判定、Recovery Evaluation、将来のTest Runnerが同じ意味で解釈できるようにする。

## 2. 基本Envelope

v1では全対応Toolが最低限以下を持つものとする。

```json
{
  "ok": true,
  "status": "success",
  "error": null,
  "warnings": []
}
```

必須field：

- `ok`
- `status`
- `error`
- `warnings`

既存Tool固有fieldはv1ではtop-levelに維持する。`data`への一括移行は行わない。

## 3. status

statusは以下の3種類とする。

- `success`
- `partial`
- `failure`

warningはstatusにしない。

### success

要求された処理範囲を完全に処理した。

```text
ok = true
status = success
error = null
```

結果0件でも、要求範囲の処理を完全に終えていればsuccess。

### partial

利用可能な結果は得られたが、**要求された処理範囲の完全性が失われている。**

```text
ok = true
status = partial
error = null
```

例：

- 安全上限到達
- 未処理領域あり
- 本来処理対象である項目の一部取得失敗
- timeoutまでの部分結果
- backendの一部失敗
- 出力容量制限による結果省略

partialはfailureではない。Agentは結果を利用したうえで、追加Actionの必要性を判断する。

### failure

Toolの主目的を達成できず、正常結果として利用できない。

```text
ok = false
status = failure
error != null
```

## 4. 必須invariant

以下を必須とする。

```text
status == success
→ ok == true
→ error == null
```

```text
status == partial
→ ok == true
→ error == null
```

```text
status == failure
→ ok == false
→ error != null
```

禁止：

```text
ok:true + error:non-null
```

```text
ok:false + status:success
```

```text
ok:false + status:partial
```

```text
status:failure + error:null
```

## 5. Runtime Stateとの対応

Tool Result Contract v1では、**success / partial / failureをRuntime履歴上でも区別することを正式方針とする。**

対応：

```text
status: success
→ TOOL_SUCCESS
```

```text
status: partial
→ TOOL_PARTIAL
```

```text
status: failure
→ TOOL_FAILED
```

Unexpected Exception：

```text
→ ERROR
```

したがって、`partial`を`TOOL_SUCCESS`へまとめない。

理由：

- Test Runnerで完全成功率と部分成功率を分離するため
- Recovery分析で「利用可能な途中結果」と「完全成功」を区別するため
- Agent Loopの品質評価を二値化しすぎないため
- 将来の進展 / 停滞 / 後退評価へ利用可能にするため

`TOOL_PARTIAL`のRuntime実装自体は今回行わない。

後続実装工程で、Runtime State、history、tests、Agent integrationを変更する。

## 6. warning

warningはstatusではなく付加情報とする。

形式：

```json
{
  "code": "scan_limit_reached",
  "message": "検索可能ファイル数が上限200件に到達しました",
  "details": {
    "scanned": 200,
    "limit": 200
  },
  "source": "search_files"
}
```

必須：

- `code`
- `message`

optional：

- `details`
- `source`

`warnings`は常にarrayとする。

## 7. error

v1 producerは構造化errorを返す。

```json
{
  "code": "path_not_found",
  "message": "指定されたファイルが存在しません",
  "details": {
    "path": "example.txt"
  }
}
```

必須：

- `code`
- `message`

optional：

- `details`

以下を含めない。

- secret
- token
- 不要なローカル絶対path
- 生stack trace

移行期間中consumerは、`null`、legacy string、v1 objectを受理可能とする。ただしv1移行済みproducerはobjectを使用する。

## 8. completeness

以下を共通optional fieldとする。

- `truncated`
- `has_more`
- `next_offset`
- `next_cursor`
- `resume_token`

### truncated

**今回要求された結果そのものが、上限等によって一部省略された。**

### has_more

元データまたは結果に続きが存在すると判明している。

したがって、次は合法である。

```text
truncated:false
has_more:true
```

例：`read_file(path, offset=1, limit=10)`で要求された10行を完全取得したが、ファイルには11行目以降がある場合。

```text
status: success
truncated: false
has_more: true
next_offset: 11
```

## 9. excludedとskippedの区別

検索・一覧・解析系Toolでは、**仕様上の正常な除外**と**本来処理対象だったが処理できなかった項目**を区別する。

### excluded

Tool仕様・Policy上、最初から処理対象外である項目。

例：

- binary file
- `.git`
- `node_modules`
- 明示的除外directory
- Tool仕様上対象外のfile type

推奨形式：

```json
{
  "excluded": {
    "total": 15,
    "reasons": {
      "binary": 12,
      "excluded_directory": 3
    }
  }
}
```

正常なexcludedだけでは原則として`partial`にしない。要求されたTool仕様上の探索範囲を完全に処理できていれば、`status:success`でよい。

### skipped

本来処理対象だったが、実行上の理由で処理できなかった項目。

例：

- permission denied
- unexpected read failure
- stat failure
- 一時的I/O error

推奨形式：

```json
{
  "skipped": {
    "total": 2,
    "reasons": {
      "unreadable": 1,
      "stat_failed": 1
    }
  }
}
```

skippedにより要求範囲の完全性が失われた場合、`status:partial`とする。

## 10. oversizedの扱い

`oversized`についてはTool仕様によって分類が変わり得る。

Tool Contractとして「256 KiB以下のテキストファイルのみ検索対象」と明示されている場合、256 KiB超は`excluded`として扱える。

一方、ユーザー要求上は検索対象であるにもかかわらず、内部安全制限で処理できなかった場合、結果完全性が失われるため、`skipped`またはlimit由来のpartialとして扱う。

Tool固有仕様に理由を明示すること。

## 11. Empty Result

結果0件はfailureではない。

```json
{
  "ok": true,
  "status": "success",
  "error": null,
  "warnings": [],
  "match_count": 0
}
```

要求範囲を完全に検索した結果0件ならsuccess。要求範囲を完全検索できていない状態で0件ならpartialになり得る。

## 12. Expected Failure / Unexpected Exception

### Expected Failure

通常運用上予測可能な失敗。

例：

- invalid path
- workspace外
- permission denied
- file not found
- 安全に処理できるtimeout
- API完全失敗
- 必須外部command利用不能

Result：

```text
ok:false
status:failure
error:{...}
```

### Unexpected Exception

Tool内部bug・想定外型・壊れた前提等。

Toolが無条件に握り潰さない。

Runtimeは`ERROR`を記録した後、既存例外方針に従って再送出する。

Tool Result failureとRuntime ERRORは別概念とする。

## 13. 判定責任

### Tool

- Envelope生成
- status判定
- completeness判定
- excluded/skipped判定
- Expected Failure構造化

### Agent

`status`を正本として扱う。

- success → 通常継続
- partial → Resultを利用し、追加Actionを判断
- failure → Tool Failureとして扱う

legacy Resultはnormalizer経由で扱う。

### Runtime

- success → `TOOL_SUCCESS`
- partial → `TOOL_PARTIAL`
- failure → `TOOL_FAILED`
- unexpected exception → `ERROR`

### UI

`error`のtruthinessで成否判定しない。`status`を正本とする。

表示上も最低限、success、partial、failureを区別できる設計とする。

### Recovery

- failure → Failure Evaluation候補
- partial → Tool Execution Failureではない
- partialからGoal未達の場合はAgentによる追加Action候補
- exception → Runtime ERRORからFailure分類

ただし将来、**partial状態の反復・停滞**をRecovery判断材料へ利用できるよう情報を保持する。

## 14. Test Runnerへの利用

Test Runnerでは最低限、success数、partial数、failure数、error数を分離集計可能にする。

例：

```text
100 trials

success: 72
partial: 18
failure: 8
error: 2
```

単純な成功率だけでなく、完全成功率、利用可能結果率、Tool Failure率、Runtime Error率を計算可能な構造を目指す。

## 15. backward compatibility

v1では破壊的変更を抑えるため、次を行う。

- `ok`を維持
- Tool固有top-level fieldを維持
- legacy string errorをconsumer側で一時受理

ただしv1対応producerは新Contractを生成する。

共通normalizerとstrict validatorを分離する。

## 16. File Tool適用原則

### read_file

明示された範囲を完全取得した場合は`status:success`とする。

ファイルに続きがあっても`has_more:true`で表現し、partialとはしない。

### list_files

件数上限により要求範囲を処理しきれない場合は`status:partial`とする。

### search_files

scan上限・match上限で要求範囲を完全処理できない場合は`status:partial`とする。

正常な仕様除外だけの場合は`status:success`とする。

本来処理対象のread/stat failure等が存在する場合は`status:partial`とする。

## 17. 現行仕様からの主要変更

以下を後続実装対象とする。

- `ok:true + error`の廃止
- `status`必須化
- `warnings`必須化
- error object化
- Partial Success正式導入
- `TOOL_PARTIAL` Runtime State導入
- excluded / skipped分離
- completeness情報追加
- Agent/UI/Recoveryのstatus基準統一
- common normalizer / validator追加
