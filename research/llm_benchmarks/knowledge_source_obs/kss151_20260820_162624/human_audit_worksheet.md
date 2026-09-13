# KSS-1.5.1 人手監査ワークシート（日本語版）

**状態:** `human_audit_status = pending` **／** `routing_ready = false`

> **今回調べたいのは「AIが最終的に成功したか」ではありません。**
>
> AIが検索で取得したページの中に、本来なら回答に使える情報が存在していたのに、
> それをAIが捨てたり、後段で利用できなかったケースがあったかを調べます。
>
> したがって、「run_success = false」（最終失敗）でも、その検索結果の中に答えが
> 存在している可能性があります。
>
> 逆に、`answer_presence = core` でも、それだけで「AIが成功すべきだった」と
> 断定するものではありません。

AIの自動判定（heuristic）は**正解ではありません**。必ず人間が記入してください。
この監査結果だけを理由に routing や confidence 閾値は実装しません。

## 用語の説明（記入時に参照）

### human_label（この検索結果は質問に役立つか）

- **DIRECT（直接的な回答）**：質問に対する答えがほぼそのまま書かれている
- **CORE（核心的な情報）**：これを使えば回答を組み立てられる
- **RELATED（関連情報）**：関連ではあるが、質問への回答としては弱い
- **IRRELEVANT（無関係）**：質問とはほぼ無関係
- **MISLEADING（誤導の可能性）**：関連しているように見えるが、回答を誤らせる可能性がある
- **UNKNOWN（判断できない）**：判断できない

### answer_presence（このページの中に、質問の答えはあるか）

「この検索結果の中に、質問への答えが存在するか」を判定します。

- **direct（直接ある）**：答えが直接存在する
- **core（核心がある）**：答えそのものではないが、回答の核心となる情報がある
- **related（関連のみ）**：関連情報はあるが、答えとしては不十分
- **none（なし）**：答えにつながる情報がない
- **misleading（誤導）**：誤った方向へ導く情報
- **unknown（不明）**：判断できない

### source_quality（情報源として信頼できるか）

- **official（公式）**：公式情報
- **authoritative（権威ある情報）**：公的機関・メーカー等の権威ある情報
- **reputable_secondary（信頼できる二次情報）**：信頼性の高い二次情報
- **ordinary（一般）**：一般的な情報源
- **unknown（不明）**：判断できない
- **unreliable（低い）**：信頼性が低い

---

## A. 捨てられた検索結果の監査（全 9 件）

**目的:** AIが捨てた検索結果の中に、本当に使える情報があったか？

今回は9件すべて確認します。

### 1. 監査ID `k151_37c38d37f2` ／ ケース `disk_usage` ／ ラウンド 1

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: MBR2GPT
- URL: [https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt](https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt)
- ドメイン: `learn.microsoft.com`
- 抜粋: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition style without modifying or deleting data on the disk. The tool runs from a Windows Preinstallation Environment (Windows PE) command prompt, but can also be run from the.
- 順位 / hit_score: 1 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `not_relevant_low_score`
- AIの自動判定 heuristic（参考・正解ではない）: `related`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: **IRRELEVANT**
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: **none**
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: **official**
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: コマンド名がMBR2GPT← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `false`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 2. 監査ID `k151_5f65367132` ／ ケース `disk_usage` ／ ラウンド 1

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: diskpart
- URL: [https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart)
- ドメイン: `learn.microsoft.com`
- 抜粋: Parameters You can run the following commands from the Diskpart command interpreter: Command Description active Marks the disk's partition with focus, as active. add Mirrors the simple volume with focus to the specified disk. assign Assigns a drive letter or mount point to the volume with focus. attach vdisk Attaches (sometimes called mounts or.
- 順位 / hit_score: 2 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `not_relevant_low_score`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 3. 監査ID `k151_9c99470ad3` ／ ケース `disk_usage` ／ ラウンド 1

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Set up a Dev Drive on Windows 11
- URL: [https://learn.microsoft.com/en-us/windows/dev-drive/](https://learn.microsoft.com/en-us/windows/dev-drive/)
- ドメイン: `learn.microsoft.com`
- 抜粋: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- 順位 / hit_score: 3 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `irrelevant_token:dev drive`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 4. 監査ID `k151_f6f1ed7f26` ／ ケース `disk_usage` ／ ラウンド 1

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Select a disk type for Azure IaaS VMs - managed disks - Azure Virtual Machines
- URL: [https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types)
- ドメイン: `learn.microsoft.com`
- 抜粋: Azure managed disk types Summarize this article for me In this article Applies to: ✔️ Linux VMs ✔️ Windows VMs ✔️ Flexible scale sets ✔️ Uniform scale sets Azure managed disks currently offers five disk types, each intended to address a specific customer scenario: Ultra Disks Premium SSD v2 Premium SSDs (solid-state drives) Standard SSDs Standard.
- 順位 / hit_score: 4 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `not_relevant_low_score`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 5. 監査ID `k151_d27fe98442` ／ ケース `disk_usage` ／ ラウンド 1

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Point-in-time restore for Windows
- URL: [https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore](https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore)
- ドメイン: `learn.microsoft.com`
- 抜粋: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults Options Editions eligible to configure Feature On/Off See below* On, Off Home, Pro, Enterprise Restore point frequency (approximate) Every 24 hours 4, 6, 12, 16, 24.
- 順位 / hit_score: 5 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `not_relevant_low_score`
- AIの自動判定 heuristic（参考・正解ではない）: `related`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 6. 監査ID `k151_f29bdceb53` ／ ケース `disk_usage` ／ ラウンド 3

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: output status disk disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Set up a Dev Drive on Windows 11
- URL: [https://learn.microsoft.com/en-us/windows/dev-drive/](https://learn.microsoft.com/en-us/windows/dev-drive/)
- ドメイン: `learn.microsoft.com`
- 抜粋: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- 順位 / hit_score: 3 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `irrelevant_token:dev drive`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 7. 監査ID `k151_35c7bac28a` ／ ケース `disk_usage` ／ ラウンド 4

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: output status disk disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Set up a Dev Drive on Windows 11
- URL: [https://learn.microsoft.com/en-us/windows/dev-drive/](https://learn.microsoft.com/en-us/windows/dev-drive/)
- ドメイン: `learn.microsoft.com`
- 抜粋: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- 順位 / hit_score: 3 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `irrelevant_token:dev drive`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 8. 監査ID `k151_9c36e9e1ad` ／ ケース `disk_usage` ／ ラウンド 5

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: output status disk disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Set up a Dev Drive on Windows 11
- URL: [https://learn.microsoft.com/en-us/windows/dev-drive/](https://learn.microsoft.com/en-us/windows/dev-drive/)
- ドメイン: `learn.microsoft.com`
- 抜粋: See the blog post: Dev Drive for Performance Improvements in Visual Studio and Dev Boxes for some average improvement measurements across common dev operations. How to set up a Dev Drive To set up a new Dev Drive, open Windows Settings and navigate to System > Storage > Advanced Storage Settings > Disks & volumes. Prerequisites Windows 11, Build.
- 順位 / hit_score: 3 / 0

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `irrelevant_token:dev drive`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

### 9. 監査ID `k151_558cad72b5` ／ ケース `memory_usage` ／ ラウンド 1

#### 質問

Windowsのメモリ使用率を取得するToolを作ってください。

- 検索クエリ: wmic powershell Windows memory usage percent PowerShell
- 最終結果: pass=`True` ／ fail_stage=`None` ／ stop=`findings_complete`

#### 検索結果

- タイトル: Protect Dev Drive using performance mode - Microsoft Defender for Endpoint
- URL: [https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode](https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode)
- ドメイン: `learn.microsoft.com`
- 抜粋: Note Using performance mode doesn't apply to high cpu or high memory usage scenarios with Microsoft Defender Antivirus services (MsMpEng.exe, WinDefend, or Antimalware Service Executable). If you're troubleshooting a high cpu usage, instead use the Microsof... Select Apply, then select OK. Manage performance mode with PowerShell Use PowerShell to.
- 順位 / hit_score: 2 / 1

#### AIはどう扱ったか

- **捨てた検索結果（DROPPED）**
- 捨てた理由 drop_reason: `irrelevant_token:dev drive`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文

⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）

- 記入欄: `missing`
- `true`：捨てるべきではなかった
- `false`：捨てて問題なかった
- `unknown`：判断できない
- その他メモ notes: `missing`

---

## B. 失敗したケースで残っていた検索結果の監査（12 件）

**目的:** AIが残した検索結果は、本当に質問への回答に役立つものだったか？

（失敗ケースで、AIのheuristicが core/direct としたものを優先。URL重複は除外済み）

### 1. 監査ID `k151_9a38b8cb64` ／ ケース `cpu_temperature` ／ ラウンド 1

#### 質問

WindowsのCPU温度を取得するToolを作ってください。

- 検索クエリ: wmic powershell Win32_Processor LoadPercentage
- 最終結果: pass=`False` ／ fail_stage=`judge` ／ stop=`max_research_rounds`

#### 検索結果

- タイトル: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- URL: [https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process)
- ドメイン: `learn.microsoft.com`
- 抜粋: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter retrieves pwsh processes and the invoked GetOwner() method returns information on the process's Domain and User. For more information, see: Example 8: Find the owner of a.
- 順位 / hit_score: 1 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": true, "candidate_index": 1, "token_overlap": 1, "command": "powershell"}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 2. 監査ID `k151_4ea8c4fb7f` ／ ケース `cpu_temperature` ／ ラウンド 1

#### 質問

WindowsのCPU温度を取得するToolを作ってください。

- 検索クエリ: wmic powershell Win32_Processor LoadPercentage
- 最終結果: pass=`False` ／ fail_stage=`judge` ／ stop=`max_research_rounds`

#### 検索結果

- タイトル: Sample scripts for system administration - PowerShell
- URL: [https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration](https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration)
- ドメイン: `learn.microsoft.com`
- 抜粋: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static classes and methods Getting WMI objects with Get-CimInstance Manipulating items directly Managing computers How-To Guide Changing computer state Collecting information.
- 順位 / hit_score: 2 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": true, "candidate_index": 0, "token_overlap": 2, "command": "powershell"}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 3. 監査ID `k151_c8d65446ca` ／ ケース `cpu_temperature` ／ ラウンド 1

#### 質問

WindowsのCPU温度を取得するToolを作ってください。

- 検索クエリ: wmic powershell Win32_Processor LoadPercentage
- 最終結果: pass=`False` ／ fail_stage=`judge` ／ stop=`max_research_rounds`

#### 検索結果

- タイトル: Get-Process (Microsoft.PowerShell.Management) - PowerShell
- URL: [https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process](https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process)
- ドメイン: `learn.microsoft.com`
- 抜粋: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows では、Get-Processの代わりに、PowerShell で Windows Management Instrumentation (WMI) Win32_Process クラスを使用できます。. 例 8: プロセスの所有者を検索する Get-CimInstance Process オブジェクトの既定の表示は、次の列を含むテーブル...
- 順位 / hit_score: 3 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 4. 監査ID `k151_2c62399581` ／ ケース `cpu_temperature` ／ ラウンド 1

#### 質問

WindowsのCPU温度を取得するToolを作ってください。

- 検索クエリ: wmic powershell Win32_Processor LoadPercentage
- 最終結果: pass=`False` ／ fail_stage=`judge` ／ stop=`max_research_rounds`

#### 検索結果

- タイトル: システム管理のサンプル スクリプト - PowerShell
- URL: [https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration](https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration)
- ドメイン: `learn.microsoft.com`
- 抜粋: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピューターの状態を変更する コンピューターに関する情報の収集 FilterHashtable を使った Get-WinEvent クエリの作成 プロセスとサービスの管理 攻略ガイド Process コマンドレットによるプロセスの管理 サービスの管理 プリンターの操作 ネットワーク関連タスクの実行 ソフトウェア インストールの操作 実行...
- 順位 / hit_score: 4 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 5. 監査ID `k151_b59aa1831d` ／ ケース `cpu_temperature` ／ ラウンド 1

#### 質問

WindowsのCPU温度を取得するToolを作ってください。

- 検索クエリ: wmic powershell Win32_Processor LoadPercentage
- 最終結果: pass=`False` ／ fail_stage=`judge` ／ stop=`max_research_rounds`

#### 検索結果

- タイトル: Stop-Process (Microsoft.PowerShell.Management) - PowerShell
- URL: [https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process](https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/stop-process)
- ドメイン: `learn.microsoft.com`
- 抜粋: 既定では、Stop-Process は、現在のユーザーが所有していないプロセスを停止する前に確認を求められます。. プロセスの所有者を見つけるには、Get-CimInstance コマンドレットを使用してプロセスを表す Win32_Process オブジェクトを取得し、そのオブジェクトの GetOwner メソッドを使用します。. プロセスの PID を見つけるには、「Get-Process」と入力します。. By default, Stop-Process prompts for confirmation before stopping any process th... To find the owner of a process, use the Get-CimInstance ...
- 順位 / hit_score: 5 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 6. 監査ID `k151_b22d0523aa` ／ ケース `disk_usage` ／ ラウンド 3

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: output status disk disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: diskpart
- URL: [https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart)
- ドメイン: `learn.microsoft.com`
- 抜粋: Parameters You can run the following commands from the Diskpart command interpreter: Command Description active Marks the disk's partition with focus, as active. add Mirrors the simple volume with focus to the specified disk. assign Assigns a drive letter or mount point to the volume with focus. attach vdisk Attaches (sometimes called mounts or.
- 順位 / hit_score: 2 / 0

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 7. 監査ID `k151_9172a54373` ／ ケース `disk_usage` ／ ラウンド 3

#### 質問

Windowsのディスク使用率を取得するToolを作ってください。

- 検索クエリ: output status disk disk
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Select a disk type for Azure IaaS VMs - managed disks - Azure Virtual Machines
- URL: [https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types)
- ドメイン: `learn.microsoft.com`
- 抜粋: Azure managed disk types Summarize this article for me In this article Applies to: ✔️ Linux VMs ✔️ Windows VMs ✔️ Flexible scale sets ✔️ Uniform scale sets Azure managed disks currently offers five disk types, each intended to address a specific customer scenario: Ultra Disks Premium SSD v2 Premium SSDs (solid-state drives) Standard SSDs Standard.
- 順位 / hit_score: 4 / 0

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 8. 監査ID `k151_3199dc2315` ／ ケース `gpu_vram_usage` ／ ラウンド 1

#### 質問

GPU VRAMの使用量をMB単位で取得するToolを作ってください。

- 検索クエリ: nvidia-smi nvidia-smi query gpu
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: GPU Utilization - Microsoft Q&A
- URL: [https://learn.microsoft.com/en-us/answers/questions/1696159/gpu-utilization](https://learn.microsoft.com/en-us/answers/questions/1696159/gpu-utilization)
- ドメイン: `learn.microsoft.com`
- 抜粋: For querying GPU utilization, a more common method is to use the nvidia-smi command-line tool to view GPU utilization, temperature, memory usage, etc. For more information about NVIDIA-SMI, please refer to the following links: System Management Interface SMI | NVIDIA Developer How-to-guide: Using nvidia-smi on host to monitor GPU behavior with.
- 順位 / hit_score: 1 / 2

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": true, "candidate_index": 0, "token_overlap": 2, "command": "nvidia-smi"}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 9. 監査ID `k151_557527ce0c` ／ ケース `gpu_vram_usage` ／ ラウンド 1

#### 質問

GPU VRAMの使用量をMB単位で取得するToolを作ってください。

- 検索クエリ: nvidia-smi nvidia-smi query gpu
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: How I can allocate full GPU to a python/anaconda ? - Microsoft Q&A
- URL: [https://learn.microsoft.com/en-us/answers/questions/4131160/how-i-can-allocate-full-gpu-to-a-python-anaconda](https://learn.microsoft.com/en-us/answers/questions/4131160/how-i-can-allocate-full-gpu-to-a-python-anaconda)
- ドメイン: `learn.microsoft.com`
- 抜粋: ..., P0, 67, 95 %, 74 %, 46068 MiB, 31550 MiB, 14241 MiB 2023/07/08 00:11:35.950, P0, 67, 91 %, 61 %, 46068 MiB, 31550 MiB, 14241 MiB C:\Users\Administrator>nvidia-smi Sat Jul  8 00:06:34 2023 +-----------------------------------------------------------------------------+ | NVIDIA-SMI 518.03       Driver Version: 518.03       CUDA Version: 11.7.
- 順位 / hit_score: 2 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": true, "candidate_index": 1, "token_overlap": 2, "command": "python"}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 10. 監査ID `k151_d2fd959ec4` ／ ケース `gpu_vram_usage` ／ ラウンド 1

#### 質問

GPU VRAMの使用量をMB単位で取得するToolを作ってください。

- 検索クエリ: nvidia-smi nvidia-smi query gpu
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Linux 用の N シリーズ GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
- URL: [https://learn.microsoft.com/ja-jp/azure/virtual-machines/linux/n-series-driver-setup](https://learn.microsoft.com/ja-jp/azure/virtual-machines/linux/n-series-driver-setup)
- ドメイン: `learn.microsoft.com`
- 抜粋: NVIDIA GPU ドライバー拡張機能は、N シリーズ VM に適切な NVIDIA コンピューティング統合デバイス アーキテクチャ (CUDA) または GRID ドライバーをインストールします。. サポートされているオペレーティング システム (OS) と展開の手順については、 NVIDIA GPU ドライバー拡張機能のドキュメントを参照してください。. NVIDIA GPU ドライバーを手動でインストールするには、この記事で説明されている手順に従います。. CUDA ドライバーのインストールを確認する nvidia-smi を実行します。. ドライバーがインストールされている場合、NVIDIA SMI は 、VM で GPU ワークロードを実行するまで GPU-Util を N...
- 順位 / hit_score: 3 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 11. 監査ID `k151_38a9f67fea` ／ ケース `gpu_vram_usage` ／ ラウンド 1

#### 質問

GPU VRAMの使用量をMB単位で取得するToolを作ってください。

- 検索クエリ: nvidia-smi nvidia-smi query gpu
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: Windows用の N シリーズ NVIDIA GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
- URL: [https://learn.microsoft.com/ja-jp/azure/virtual-machines/windows/n-series-driver-setup](https://learn.microsoft.com/ja-jp/azure/virtual-machines/windows/n-series-driver-setup)
- ドメイン: `learn.microsoft.com`
- 抜粋: GRID ドライバーのインストールを確認す... nvidia-smi を実行します。. ドライバーがインストールされている場合、NVIDIA SMI は 、VM で GPU ワークロードを実行するまで GPU-Util を N/A として一覧表示します。. AzureでWindows ServerまたはWindowsを実行している N シリーズ VM 用に NVIDIA GPU ドライバーを設定する方法. Install NVIDIA GPU Drivers on N-series VMs Running Windows Summarize this article for me In this article Applies to: ✔️ Windows VMs To take a...
- 順位 / hit_score: 4 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

### 12. 監査ID `k151_64a56e297c` ／ ケース `gpu_vram_usage` ／ ラウンド 1

#### 質問

GPU VRAMの使用量をMB単位で取得するToolを作ってください。

- 検索クエリ: nvidia-smi nvidia-smi query gpu
- 最終結果: pass=`False` ／ fail_stage=`research` ／ stop=`stagnation`

#### 検索結果

- タイトル: NC_RTXPRO6000BSE_v6 サイズ シリーズの概要 - Azure Virtual Machines
- URL: [https://learn.microsoft.com/ja-jp/azure/virtual-machines/sizes/gpu-accelerated/nc-rtxpro6000-bse-v6-series-overview](https://learn.microsoft.com/ja-jp/azure/virtual-machines/sizes/gpu-accelerated/nc-rtxpro6000-bse-v6-series-overview)
- ドメイン: `learn.microsoft.com`
- 抜粋: オムニバース Isaac-Sim は NC... オムニバース Isaac-Sim 6.0 は NCv6 でサポートされています。. NCv6 の nvidia-smi を使用すると、電力や熱テレメトリが表示されないのはなぜですか. これは、SR-IOV モードの制限です。. 詳細については、「 HPC および GPU VM に関する既知の問題のトラブルシューティング」を参照してください。. NC RTX PRO 6000 Blackwell v6 sizes series overview Summarize this article for me In this article The NCv6-series is a single virtual machine (VM) fam...
- 順位 / hit_score: 5 / 1

#### AIはどう扱ったか

- **残した検索結果（KEPT）**
- 捨てた理由 drop_reason: `kept`
- AIの自動判定 heuristic（参考・正解ではない）: `core`
- candidateとの接続: `{"linked": false}`

#### 人間が判断すること

① **この検索結果は質問に役立つか？**（`human_label`）

- 記入欄: `missing`
- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**

② **このページの中に、質問の答えはあるか？**（`answer_presence`）

- 記入欄: `missing`
- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**

③ **情報源として信頼できるか？**（`source_quality`）

- 記入欄: `missing`
- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**

④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）

- 場所: `missing` ← 見出し・段落など。分からなければ `不明`
- 参照メモ: `missing` ← 再確認できる短い手がかり

⑤ **なぜそう判断したか？**（`human_rationale`）

- 記入欄: `missing` ← 日本語で1～2文
- その他メモ notes: `missing`

---

## C. 失敗した場所の監査

**目的:** Web検索から最終回答までのどこで情報が失われた可能性があるか？

選択肢:

- **SEARCH_MISS**：検索段階で見つけられなかった
- **DROP_ERROR**：検索結果を誤って捨てた
- **CANDIDATE_MISS**：候補として拾えなかった
- **VERIFY_ERROR**：検証段階で失敗した
- **USABLE_CONVERSION_ERROR**：使える情報に変換できなかった
- **JUDGE_ERROR**：LLMの判断で失敗した
- **PROGRESS_ERROR**：調査継続・終了判断で失敗した
- **PROPOSAL_ERROR**：Tool提案段階で失敗した
- **UNKNOWN**：判断できない

主因と副因がある場合は `primary_loss_stage` / `secondary_loss_stage` に分けて記入。

### ケース `cpu_temperature`

- 最終結果（run_success）: **失敗**（`False`）※これは「ページに答えがあったか」とは別
- 失敗段階 fail_stage / 停止理由: `judge` / `max_research_rounds`
- 質問: WindowsのCPU温度を取得するToolを作ってください。
- **answer_present_in_web**（Web上に答えがあったか）: `missing`
  - 記入: `true`（あった） / `false`（なかった） / `unknown`（不明）
  - ※ここが true でも「成功すべき」とは断定しない
- **primary_loss_stage**（主に失われた段階）: `missing`
- **secondary_loss_stage**（副次的な段階）: `missing`
- **notes**（メモ）: `missing`

### ケース `disk_usage`

- 最終結果（run_success）: **失敗**（`False`）※これは「ページに答えがあったか」とは別
- 失敗段階 fail_stage / 停止理由: `research` / `stagnation`
- 質問: Windowsのディスク使用率を取得するToolを作ってください。
- **answer_present_in_web**（Web上に答えがあったか）: `missing`
  - 記入: `true`（あった） / `false`（なかった） / `unknown`（不明）
  - ※ここが true でも「成功すべき」とは断定しない
- **primary_loss_stage**（主に失われた段階）: `missing`
- **secondary_loss_stage**（副次的な段階）: `missing`
- **notes**（メモ）: `missing`

### ケース `gpu_usage`

- 最終結果（run_success）: **失敗**（`False`）※これは「ページに答えがあったか」とは別
- 失敗段階 fail_stage / 停止理由: `proposal` / `None`
- 質問: GPUの使用率を取得するToolを作ってください。
- **answer_present_in_web**（Web上に答えがあったか）: `missing`
  - 記入: `true`（あった） / `false`（なかった） / `unknown`（不明）
  - ※ここが true でも「成功すべき」とは断定しない
- **primary_loss_stage**（主に失われた段階）: `missing`
- **secondary_loss_stage**（副次的な段階）: `missing`
- **notes**（メモ）: `missing`

### ケース `gpu_vram_usage`

- 最終結果（run_success）: **失敗**（`False`）※これは「ページに答えがあったか」とは別
- 失敗段階 fail_stage / 停止理由: `research` / `stagnation`
- 質問: GPU VRAMの使用量をMB単位で取得するToolを作ってください。
- **answer_present_in_web**（Web上に答えがあったか）: `missing`
  - 記入: `true`（あった） / `false`（なかった） / `unknown`（不明）
  - ※ここが true でも「成功すべき」とは断定しない
- **primary_loss_stage**（主に失われた段階）: `missing`
- **secondary_loss_stage**（副次的な段階）: `missing`
- **notes**（メモ）: `missing`

---

## 記入後の手順

1. このワークシートの内容を `ground_truth_labels.json` に転記する（または `ground_truth_template.json` の同名フィールドを編集）。
2. 集計: `python _kss151_human_audit.py --apply-labels <filled.json> --out-dir <この実験ディレクトリ>`
3. サンプル数が少ない場合、精度は「観測サンプル／小標本の見積もり」として扱う。
4. **この結果だけで routing や confidence 閾値は実装しない。**

