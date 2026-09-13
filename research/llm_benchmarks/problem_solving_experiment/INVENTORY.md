# 既存 Tool 棚卸し（実験用）

FA 仕様ではない。Registry 登録と「関数として存在する」を分ける。

| 能力 | 既存Tool / 既存関数 | 既存で代用可能 | 不足 | 備考 |
| --- | --- | --- | --- | --- |
| Failure情報 | `test_tool`, `validate_tool_result`（Registry あり） | 実行・検査は可。ただし「今の Failure スナップショットを読む」専用 Tool は無い | 実験用ラッパが必要 | Test Result Schema は変更しない。実験セッションが保持した dict を読む |
| File Read | `tools.file.workspace.read_file`（offset/limit あり） | **可** | Registry 未登録。agent SYSTEM_PROMPT は言及するが `registry/tools.json` に無い | 新規実装しない。実験ディスパッチから既存関数を呼ぶ |
| Code Read | 同上 `read_file` | **可**（行指定・周辺は offset/limit） | コード専用 Tool は未確定で不要 | File Read と同一関数 |
| Repository Search | `tools.file.workspace.search_files` / `list_files` | **可**（文字列・glob・ファイル名） | Registry 未登録 | クラス/関数は文字列検索で代用 |
| Definition / Reference | 専用 LSP は無い | search_files で `def` / import 文字列を探す代用 | 参照グラフは無い | 別 Tool にしない。実験で LLM が何を要求するか見る |
| PDF Read | 本番 Tool なし。TDA fixture のみ | **不可** | 実験用が必要。pypdf 等は依存に無い | ライブラリ無ければ `pdf_library_not_installed` を返す |
| Web Search | `search_web`, `read_url_text`（Registry・agent） | **可** | 自動検索規則は作らない | 実験で LLM が選んだときだけ呼ぶ |
| Environment | `get_system_summary`, `get_cpu_status`, `get_memory_status`, `get_gpu_status` | 部分可（時刻/CPU/RAM/GPU） | python executable / venv / cwd は Registry Tool に無い。`verified_environment()` はベンチ関数 | 実験用に既存関数を束ねて読む。本番 Environment 経路は変更しない |
| Process / Runtime | `get_gpu_processes` | GPU プロセスは **可** | OS 全プロセス一覧は無い | 既存を使う。新規の汎用 process 一覧は作らない |
| Test / Execute | `test_tool`（Registry の Tool を本番ファイルで実行） | 登録済み Tool の再実行は可 | LLM 案を本番 `cpu_status.py` / `apply_repair` へ無条件適用してはいけない | 実験用に一時ファイル実行を追加 |
| Diff / Change | `ai_tool.chat_interface.dev_readonly.git_snapshot` | **可**（git 読み取り） | Registry Tool ではない | 新規 git 実装はしない。実験から既存関数を呼ぶ |
| Human HELP | 専用 Tool なし。方針 JSON に人間確認の言及はある | 実験上の記録口が無い | 実験用に「HELP 要求を記録する」だけ | 複雑な API は作らない |
