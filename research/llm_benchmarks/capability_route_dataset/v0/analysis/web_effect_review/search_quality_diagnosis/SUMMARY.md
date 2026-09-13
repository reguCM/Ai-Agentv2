# SUMMARY

## ボトルネック仮説（人間確認前・断定しない）

| 分類 | 観測 |
|------|------|
| A 候補生成 | API生0〜少数のクエリあり |
| B ranking | snippetあり脱落あり（C02等） |
| C 内容取得 | **最多**。return複数でもsnippet空 |
| D LLM受け渡し | 件数削減なし |

## 日英比較

| theme | ja query | ja api | ja ret | ja snip+ | en query | en api | en ret | en snip+ |
|-------|----------|-------:|-------:|---------:|----------|-------:|-------:|---------:|
| drivers_license_jp | `日本の運転免許 取得方法` | 0 | 0 | 0 | `Japan driving license how to get` | 0 | 0 | 0 |
| ollama | `Ollamaとは` | 0 | 0 | 0 | `Ollama` | 18 | 3 | 1 |
| python_313 | `Python 3.13 新機能` | 0 | 0 | 0 | `Python 3.13 new features` | 0 | 0 | 0 |
| rtx3060_current | `RTX 3060 現在 立ち位置` | 0 | 0 | 0 | `GeForce RTX 3060 current status` | 0 | 0 | 0 |