# Ollama モデルパス復旧

**日付:** 2026-08-30  
**判定:** 復旧成功（`ollama list` に `deepseek-coder-v2:16b` あり）  
**Chat / 実LLMテスト:** 未実施（指示どおり停止）

---

## 原因

起動中の `ollama serve` が次を見ていた。

```text
OLLAMA_MODELS = C:\Users\e1n07\.ollama\models
blobs: 0
```

一方、実データは `D:\ollama\models`。  
ユーザー環境変数 `OLLAMA_MODELS=D:\ollama\models` は既に設定済みだったが、**Ollama トレイアプリ（`ollama app.exe`）が子プロセスを既定パスで起動し、環境変数を上書きしていた。**

`.venv` / Python / `agent.py` は無関係。

---

## 実施したこと

1. プロセス確認: `ollama app.exe` + `ollama.exe serve`（サービスではない）
2. 実行ファイル: `C:\Users\e1n07\AppData\Local\Programs\Ollama\ollama.exe`
3. トレイアプリを止め、`ollama.exe serve` を `OLLAMA_MODELS=D:\ollama\models` 付きで起動
4. 空だった既定フォルダを、データを移さずジャンクションにした  
   `C:\Users\e1n07\.ollama\models` → `D:\ollama\models`  
   （トレイが既定パスを使っても同じデータを見る）

pull / 削除 / 移動 / 名前変更 / 別モデル切替はしていない。

---

## 復旧後の確認

`ollama list`:

```text
gemma3:12b
qwen2.5-coder:7b
qwen3:14b
deepseek-coder-v2:16b
qwen3:8b
```

`ollama show deepseek-coder-v2:16b` は architecture=deepseek2 / 15.7B を返した。

---

## 変更した設定

| 項目 | 内容 |
|------|------|
| Ollama プロセス | トレイ経由ではなく `ollama.exe serve` を D:\ 付きで再起動 |
| ジャンクション | 空の既定 `models` を `D:\ollama\models` へ |

## 変更していない設定

- `pipeline.yaml`
- `agent.py`
- Chat UI のモデル指定
- ユーザー `OLLAMA_MODELS`（もともと `D:\ollama\models`）
- モデル本体

---

## 注意

トレイアプリ `ollama app.exe` だけから起動すると、以前は既定の空フォルダを見ていた。ジャンクション後は同じデータを指す。  
ログイン直後にトレイが先に空パスで起動する再発があれば、ジャンクションが残っているか確認する。

Chat → LLM → Tool の実測は、ユーザー確認後に行う。
