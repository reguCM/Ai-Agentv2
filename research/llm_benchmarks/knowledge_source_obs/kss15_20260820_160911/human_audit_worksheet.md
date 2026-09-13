# KSS-1.5 Human Audit Worksheet

Fill human_answer_presence and human_rationale (1 line). Do not treat heuristic as ground truth. LLM Judge only after enough human labels.

entries: 69
buckets: `{"kept_other": 30, "B_success_dropped": 1, "D_failed_kept_answerish": 30, "A_failed_dropped": 8}`

## 1. aud_c2616f3655 — kept_other

- Case: `memory_usage` Round: `1`
- Final: pass=True fail_stage=None stop=findings_complete
- Original question: Windowsのメモリ使用率を取得するToolを作ってください。
- Query: wmic powershell Windows memory usage percent PowerShell
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/windows-recovery-environment--windows-re--technical-reference
- Title: Windows 回復環境 (Windows RE)
- Snippet: Windows 回復環境 (Windows RE) この記事の内容 Windows回復環境 (WinRE) は、起動できないオペレーティング システムの一般的な原因を修復できる回復環境です。. The base WinRE... Memory requirements In order to boot Windows RE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory (RAM) which can hold the entire Windows RE image (winre.wim) must be available. To optimize ...
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 2. aud_5cbe45b346 — B_success_dropped

- Case: `memory_usage` Round: `1`
- Final: pass=True fail_stage=None stop=findings_complete
- Original question: Windowsのメモリ使用率を取得するToolを作ってください。
- Query: wmic powershell Windows memory usage percent PowerShell
- Kept/Dropped: **DROPPED**
- Drop reason: `irrelevant_token:dev drive`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode
- Title: Protect Dev Drive using performance mode - Microsoft Defender for Endpoint
- Snippet: Note Using performance mode doesn't apply to high cpu or high memory usage scenarios with Microsoft Defender Antivirus services (MsMpEng.exe, WinDefend, or Antimalware Service Executable). If you're troubleshooting a high cpu usage, instead use the Microsof... Select Apply, then select OK. Manage performance mode with PowerShell Use PowerShell to.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 3. aud_fffa02e9f5 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `1`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- Rank/score: 1 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 4. aud_fdadea951b — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `1`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
- Title: Sample scripts for system administration - PowerShell
- Snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 5. aud_a673f2b289 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `1`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- Rank/score: 3 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 6. aud_1e0da476cf — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `1`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
- Title: システム管理のサンプル スクリプト - PowerShell
- Snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- Rank/score: 4 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 7. aud_67c0430a10 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `1`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process
- Title: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- Rank/score: 5 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 8. aud_cdca81970b — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `2`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- Rank/score: 1 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 9. aud_438d18e866 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `2`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
- Title: Sample scripts for system administration - PowerShell
- Snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 10. aud_0c9a33a22a — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `2`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- Rank/score: 3 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 11. aud_5244e05d28 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `2`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
- Title: システム管理のサンプル スクリプト - PowerShell
- Snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- Rank/score: 4 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 12. aud_1fa194e4b0 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `2`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process
- Title: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- Rank/score: 5 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 13. aud_8091c0ba76 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- Rank/score: 1 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 14. aud_487e4eb9fc — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
- Title: Sample scripts for system administration - PowerShell
- Snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 15. aud_d2e62fd79f — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- Rank/score: 3 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 16. aud_54b70a4469 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
- Title: システム管理のサンプル スクリプト - PowerShell
- Snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- Rank/score: 4 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 17. aud_70ea13070e — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process
- Title: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- Rank/score: 5 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 18. aud_db327b1b14 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- Rank/score: 1 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 19. aud_b44cc9fbf0 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
- Title: Sample scripts for system administration - PowerShell
- Snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 20. aud_21247f3e65 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- Rank/score: 3 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 21. aud_8ebe25f80e — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
- Title: システム管理のサンプル スクリプト - PowerShell
- Snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- Rank/score: 4 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 22. aud_e55a79c20c — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `3`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process
- Title: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- Rank/score: 5 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 23. aud_6a189c104e — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- Rank/score: 1 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 24. aud_86f6781d10 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
- Title: Sample scripts for system administration - PowerShell
- Snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 25. aud_85713a0ec1 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- Rank/score: 3 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 26. aud_d9f5b7eb09 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
- Title: システム管理のサンプル スクリプト - PowerShell
- Snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- Rank/score: 4 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 27. aud_cfed518abc — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: output status cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process
- Title: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- Rank/score: 5 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 28. aud_e90fb5caed — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- Rank/score: 1 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 29. aud_07500b33b9 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
- Title: Sample scripts for system administration - PowerShell
- Snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- Rank/score: 2 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 30. aud_a40b4cfb8c — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
- Title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- Rank/score: 3 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 31. aud_8166d7af92 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
- Title: システム管理のサンプル スクリプト - PowerShell
- Snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- Rank/score: 4 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 32. aud_52a71e73b4 — D_failed_kept_answerish

- Case: `cpu_temperature` Round: `4`
- Final: pass=False fail_stage=judge stop=max_research_rounds
- Original question: WindowsのCPU温度を取得するToolを作ってください。
- Query: A method or tool to retrieve CPU temperature on Windows cpu wmic powershell Win32_Processor LoadPercentage
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process
- Title: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- Snippet: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- Rank/score: 5 / 1
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 33. aud_96fdb83cde — A_failed_dropped

- Case: `disk_usage` Round: `1`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: disk
- Kept/Dropped: **DROPPED**
- Drop reason: `not_relevant_low_score`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt
- Title: MBR2GPT
- Snippet: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition style without modifying or deleting data on the disk. The tool runs from a Windows Preinstallation Environment (Windows PE) command prompt, but can also be run from the.
- Rank/score: 1 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 34. aud_5fd28e2214 — A_failed_dropped

- Case: `disk_usage` Round: `1`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: disk
- Kept/Dropped: **DROPPED**
- Drop reason: `not_relevant_low_score`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart
- Title: diskpart
- Snippet: Parameters You can run the following commands from the Diskpart command interpreter: Command Description active Marks the disk's partition with focus, as active. add Mirrors the simple volume with focus to the specified disk. assign Assigns a drive letter or mount point to the volume with focus. attach vdisk Attaches (sometimes called mounts or.
- Rank/score: 2 / 0
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 35. aud_d4a53a6acc — A_failed_dropped

- Case: `disk_usage` Round: `1`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: disk
- Kept/Dropped: **DROPPED**
- Drop reason: `irrelevant_token:dev drive`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/dev-drive/
- Title: Set up a Dev Drive on Windows 11
- Snippet: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- Rank/score: 3 / 0
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 36. aud_74a3cd0f56 — A_failed_dropped

- Case: `disk_usage` Round: `1`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: disk
- Kept/Dropped: **DROPPED**
- Drop reason: `not_relevant_low_score`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types
- Title: Select a disk type for Azure IaaS VMs - managed disks - Azure Virtual Machines
- Snippet: Azure managed disk types Summarize this article for me In this article Applies to: ✔️ Linux VMs ✔️ Windows VMs ✔️ Flexible scale sets ✔️ Uniform scale sets Azure managed disks currently offers five disk types, each intended to address a specific customer scenario: Ultra Disks Premium SSD v2 Premium SSDs (solid-state drives) Standard SSDs Standard.
- Rank/score: 4 / 0
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 37. aud_1f36d16b88 — A_failed_dropped

- Case: `disk_usage` Round: `1`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: disk
- Kept/Dropped: **DROPPED**
- Drop reason: `not_relevant_low_score`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore
- Title: Point-in-time restore for Windows
- Snippet: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults Options Editions eligible to configure Feature On/Off See below* On, Off Home, Pro, Enterprise Restore point frequency (approximate) Every 24 hours 4, 6, 12, 16, 24.
- Rank/score: 5 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 38. aud_680b63ebe8 — kept_other

- Case: `disk_usage` Round: `2`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 39. aud_f64bf6a70f — kept_other

- Case: `disk_usage` Round: `2`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 40. aud_ccc041dbb0 — kept_other

- Case: `disk_usage` Round: `2`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/sql/database-engine/configure-windows/server-memory-server-configuration-options
- Title: サーバー メモリ構成オプション - SQL Server
- Snippet: サーバー メモリの構成オプション この記事の内容 適用対象:SQL Server SQL Server データベース エンジンのメモリ使用率は、 min server memory (MB) と max server memory (MB)の構成設定のペアによって制限されます。. Locking pages in memory might keep the server responsive when paging memory... Establish maximum settings for each instance, being careful that the total allowance isn't more than the total physical memory ...
- Rank/score: 3 / 1
- Heuristic (not truth): `unknown`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 41. aud_c5b3902587 — kept_other

- Case: `disk_usage` Round: `2`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 42. aud_8f4a80545b — kept_other

- Case: `disk_usage` Round: `2`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 43. aud_dde78260e2 — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt
- Title: MBR2GPT
- Snippet: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition style without modifying or deleting data on the disk. The tool runs from a Windows Preinstallation Environment (Windows PE) command prompt, but can also be run from the.
- Rank/score: 1 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 44. aud_3bea0f75fc — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore
- Title: Point-in-time restore for Windows
- Snippet: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults Options Editions eligible to configure Feature On/Off See below* On, Off Home, Pro, Enterprise Restore point frequency (approximate) Every 24 hours 4, 6, 12, 16, 24.
- Rank/score: 5 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 45. aud_9746b56775 — A_failed_dropped

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **DROPPED**
- Drop reason: `irrelevant_token:dev drive`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/dev-drive/
- Title: Set up a Dev Drive on Windows 11
- Snippet: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- Rank/score: 3 / 0
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 46. aud_02139905c3 — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 47. aud_6e200b2503 — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 48. aud_9ac8d3c90b — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/sql/database-engine/configure-windows/server-memory-server-configuration-options
- Title: サーバー メモリ構成オプション - SQL Server
- Snippet: サーバー メモリの構成オプション この記事の内容 適用対象:SQL Server SQL Server データベース エンジンのメモリ使用率は、 min server memory (MB) と max server memory (MB)の構成設定のペアによって制限されます。. Locking pages in memory might keep the server responsive when paging memory... Establish maximum settings for each instance, being careful that the total allowance isn't more than the total physical memory ...
- Rank/score: 3 / 1
- Heuristic (not truth): `unknown`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 49. aud_c9c8238e46 — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 50. aud_49cf002093 — kept_other

- Case: `disk_usage` Round: `3`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 51. aud_7ef5b6da9e — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt
- Title: MBR2GPT
- Snippet: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition style without modifying or deleting data on the disk. The tool runs from a Windows Preinstallation Environment (Windows PE) command prompt, but can also be run from the.
- Rank/score: 1 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 52. aud_f551ccbcc9 — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore
- Title: Point-in-time restore for Windows
- Snippet: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults Options Editions eligible to configure Feature On/Off See below* On, Off Home, Pro, Enterprise Restore point frequency (approximate) Every 24 hours 4, 6, 12, 16, 24.
- Rank/score: 5 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 53. aud_f3c7ecf181 — A_failed_dropped

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **DROPPED**
- Drop reason: `irrelevant_token:dev drive`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/dev-drive/
- Title: Set up a Dev Drive on Windows 11
- Snippet: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- Rank/score: 3 / 0
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 54. aud_67c73c7723 — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 55. aud_6138ce7dd1 — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 56. aud_0f32f35e20 — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/sql/database-engine/configure-windows/server-memory-server-configuration-options
- Title: サーバー メモリ構成オプション - SQL Server
- Snippet: サーバー メモリの構成オプション この記事の内容 適用対象:SQL Server SQL Server データベース エンジンのメモリ使用率は、 min server memory (MB) と max server memory (MB)の構成設定のペアによって制限されます。. Locking pages in memory might keep the server responsive when paging memory... Establish maximum settings for each instance, being careful that the total allowance isn't more than the total physical memory ...
- Rank/score: 3 / 1
- Heuristic (not truth): `unknown`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 57. aud_5345bf72bd — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 58. aud_3ec12be43c — kept_other

- Case: `disk_usage` Round: `4`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 59. aud_e2b96f2b3b — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt
- Title: MBR2GPT
- Snippet: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition style without modifying or deleting data on the disk. The tool runs from a Windows Preinstallation Environment (Windows PE) command prompt, but can also be run from the.
- Rank/score: 1 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 60. aud_77a2981b43 — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore
- Title: Point-in-time restore for Windows
- Snippet: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults Options Editions eligible to configure Feature On/Off See below* On, Off Home, Pro, Enterprise Restore point frequency (approximate) Every 24 hours 4, 6, 12, 16, 24.
- Rank/score: 5 / 0
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 61. aud_1e2b5f5d7c — A_failed_dropped

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: output status disk disk
- Kept/Dropped: **DROPPED**
- Drop reason: `irrelevant_token:dev drive`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows/dev-drive/
- Title: Set up a Dev Drive on Windows 11
- Snippet: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- Rank/score: 3 / 0
- Heuristic (not truth): `core`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 62. aud_004e8aca3e — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 63. aud_c88615ddf7 — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 64. aud_c4eeca4387 — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/sql/database-engine/configure-windows/server-memory-server-configuration-options
- Title: サーバー メモリ構成オプション - SQL Server
- Snippet: サーバー メモリの構成オプション この記事の内容 適用対象:SQL Server SQL Server データベース エンジンのメモリ使用率は、 min server memory (MB) と max server memory (MB)の構成設定のペアによって制限されます。. Locking pages in memory might keep the server responsive when paging memory... Establish maximum settings for each instance, being careful that the total allowance isn't more than the total physical memory ...
- Rank/score: 3 / 1
- Heuristic (not truth): `unknown`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 65. aud_bf973dbdbd — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 66. aud_e6882a2d2c — kept_other

- Case: `disk_usage` Round: `5`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: used memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 67. aud_a32c1dbad3 — kept_other

- Case: `disk_usage` Round: `6`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 1 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 68. aud_2317a12376 — kept_other

- Case: `disk_usage` Round: `6`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
- Title: Windows PE (WinPE)
- Snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Windows Server, and other Windows operating systems. In order to boot Windows PE directly from memory (also known as RAM disk boot), a contiguous portion of physical memory.
- Rank/score: 2 / 1
- Heuristic (not truth): `related`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why

## 69. aud_77d7ab6f49 — kept_other

- Case: `disk_usage` Round: `6`
- Final: pass=False fail_stage=research stop=stagnation
- Original question: Windowsのディスク使用率を取得するToolを作ってください。
- Query: total physical memory disk disk
- Kept/Dropped: **KEPT**
- Drop reason: `kept`
- Domain/URL: `learn.microsoft.com` / https://learn.microsoft.com/ja-jp/sql/database-engine/configure-windows/server-memory-server-configuration-options
- Title: サーバー メモリ構成オプション - SQL Server
- Snippet: サーバー メモリの構成オプション この記事の内容 適用対象:SQL Server SQL Server データベース エンジンのメモリ使用率は、 min server memory (MB) と max server memory (MB)の構成設定のペアによって制限されます。. Locking pages in memory might keep the server responsive when paging memory... Establish maximum settings for each instance, being careful that the total allowance isn't more than the total physical memory ...
- Rank/score: 3 / 1
- Heuristic (not truth): `unknown`
- Human label: `missing` ← fill direct|core|lead|related|none|unknown
- Human rationale: `missing` ← 1 line why
