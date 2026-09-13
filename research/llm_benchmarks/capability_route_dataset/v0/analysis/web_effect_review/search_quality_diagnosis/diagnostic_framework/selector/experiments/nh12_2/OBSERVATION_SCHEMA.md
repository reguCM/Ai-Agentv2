# OBSERVATION_SCHEMA — NH12-2

NH12-2 では NH9 fixed observation slots を継続使用する。

## Condition B

Compression slots → mechanical mapping → NH9 slots（LLM不使用）

## Condition C/D

Compression block を Observation LLM への入力に前置する。

```text
## Mechanical Compression (pre-LLM)
- runtime: status=... value=... source=...
...
```

LLM は圧縮結果を補完・確認するのみ。圧縮と矛盾する推測は禁止。

## Slot 構造（NH9）

```json
{
  "status": "OBSERVED | NOT_OBSERVED | UNKNOWN",
  "value": true | false | null,
  "confidence": "high | medium | low",
  "evidence_reference": "compression:tool | runtime_log | ..."
}
```

## Condition D — Large LLM

HIGH/MEDIUM Gate 時のみ。役割は **slot 再観測/訂正** のみ（全体診断禁止）。
