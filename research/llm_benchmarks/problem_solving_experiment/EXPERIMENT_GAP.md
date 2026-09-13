# EXPERIMENT_GAP — 成立させたい実験との差分

実装仕様ではない。観測したい流れと現状のずれ。

成立させたい流れ:

```
Failure → 最小初期情報 → LLM
  → 追加情報が必要か → Tool 選択 → 実行 → 結果 → 再判断
  → （繰り返し）→ 修正案 → Sandbox Test → Test結果 → LLM再判断
  → 解決 / 再調査 / 別修正 / HELP
```

別々に観測したいもの: Tool利用 / 情報理解 / 修正 / Test / 再評価 / 脱出。

---

## 差分一覧

| 観測したいこと | 現状 | 差分 |
| --- | --- | --- |
| 何を LLM に渡したか後から確認 | 結果 JSON に messages / SYSTEM / Tool 結果が無い | 送信面が再構成依存。Ollama 生ログも無い |
| 最小初期情報のあと、追加は Tool 経由 | 第1 user は最小に近い。`get_current_failure` が一括で source+traceback+validation | 「どの観測を選んだか」が1 Tool に潰れる |
| Tool を選択できたか | 13名は system テキストにある。native tools ではない | 「選択できた」= テキストから JSON で名前を書いた、まで。モデルの tool calling 能力とは別 |
| Tool の用途を理解できたか | 1行 description。return schema なし | 用途不足で選ばないことと、不要で選ばないことを分離できない |
| Tool 結果で判断が変わったか | 結果は次 user に入るが、保存されない。Test 結果は戻らない | 情報理解と Test 再評価がログ上切れうる |
| 修正案 | final の `patch_source` | 会話と Test の間に LLM 再判断が無い |
| Test が何を確認したか | 例外なし = pass | 問題解決と同一視されうる |
| Test 後の再判断 | 未接続 | 流れの最後の分岐が観測できない |
| HELP | 記録口はある | 状態としては薄い |
| 停滞 | turns はあるが、同一 Tool / 同一 patch の比較構造は無い | 将来観測しにくい |

---

## 混同が起きる点

1. Tool 利用能力 ≠ JSON を書ける能力 ≠ Ollama native tools を使える能力  
2. `get_current_failure` 成功 ≠ 個別観測 Tool を選んだ  
3. `status=pass` ≠ 問題が解決した  
4. `unparsed` ≠ モデルが Tool を理解していない（形式・parser の問題が混ざる）  
5. 他 Tool 未使用 ≠ それらの Tool が不要だった
