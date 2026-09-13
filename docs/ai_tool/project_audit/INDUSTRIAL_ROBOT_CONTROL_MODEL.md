# Industrial Robot Control Model — Research / Spec Draft

**種別:** Research Record + Specification Draft（実装 Core ではない）  
**日付:** 2026-08-30  
**対象実測:** URSim Docker 5.15.2 / UR5（実機なし）  
**Production 変更:** 0  
**新規 C3:** 0（判定: 作らない）

この文書は「URSim を動かす手順」ではなく、**Agent/Tool が産業用ロボット Controller を扱うときに、何を別 Facet として考えねばならないか**を残す。

ISO 10218-1:**2011** を UR 5.15.2 世代の共通根拠とする。ISO 10218-1:**2025** の Direct/External 用語は後年改訂として記録し、5.15.2 へ適用しない。

関連: [UR_PROGRAM_VALIDATOR_PHASE_J.md](./UR_PROGRAM_VALIDATOR_PHASE_J.md)  
Research Record JSON: `docs/ai_tool/project_audit/research_records/RR_INDUSTRIAL_ROBOT_CONTROL_MODEL.json`

---

## 混同禁止（7 Facet）

| # | Facet | 意味 | 混同しやすい誤り |
|---|--------|------|------------------|
| 1 | **transport_state** | 通信できるか（TCP 接続、切断、タイムアウト） | 切断 = 操作権解放 |
| 2 | **control_authority** | 誰が Controller を操作する権利を持つか | Remote Enable = すでに Remote |
| 3 | **controller_state** | Controller 内部モード（boot, idle, running 等） | robotmode = programstate |
| 4 | **program_state** | Program / Job の実行状態 | Dashboard 受理 = 実行 |
| 5 | **power_state** | 電源 / Servo / Brake | Power On = 実行中 |
| 6 | **safety_state** | 安全系（Normal, Protective Stop, E-Stop, Fault） | Fault を Program Stop と同一視 |
| 7 | **observation** | 外部から何が観測できたか | 応答に `error` が無い = PASS |

J-1 実測: **(1) と (2) は別物**。Dashboard TCP はコマンドごとに切断されるが、`set operational mode automatic` の所有権は Controller に残る。

---

## 1. Concept Catalog（暫定名称）

作業名は **Control Authority**。ISO 2011 の **single point of control** / **local control** がメーカー横断の根拠。各社のキー名は vendor-specific。

### control_authority

| 項目 | 内容 |
|------|------|
| Common Concept | 同時に運動開始を許す制御源は一つ。ペンダント（Direct/Local）中は外部からの運動開始を拒む（ISO 10218-1:2011 5.3.5）。 |
| Vendor-specific | UR: Local / Remote（Enable は別）。FANUC: Remote/Local + TP enable + External Mode Select はモード切替源が一つ。Yaskawa: TEACH / PLAY / REMOTE キー。ABB: FlexPendant と Automatic + System Input。KUKA: T1/T2/AUT は人間、**EXT** は上位コントローラ。 |
| Version | ISO 2011。ISO 2025 は Local/Remote を Direct/External に改称（UR Safety FAQ）。**5.15.2 には 2025 用語を当てない。** |
| Evidence | ISO 10218-1:2011 3.13/3.21/5.3.5。UR User Manual Remote Control（SW5_19/SW5_20、5.15 世代に存在）。UR Forum: Dashboard から Local→Remote は安全上不可。ABB Product Spec が ISO 5.3.5 を引用。 |
| Unknown | FANUC/Yaskawa/ABB/KUKA は本環境で未実測。 |
| Conflict | KUKA EXT は「Automatic かつ External」を一つのキーに畳む。UR は Automatic と Remote を分離。 |

### operational_mode

| 項目 | 内容 |
|------|------|
| Common Concept | 教示/低速確認と、プログラム自動運転は別モード。速度・編集可否・セーフガードの扱いが変わる。 |
| Vendor-specific | UR: Manual / Automatic（パスワード未設定時 `NONE`）。FANUC: T1 / T2 / AUTO。ABB: Manual reduced / Manual high / Automatic。KUKA: T1 / T2 / AUT / EXT。Yaskawa: Teach vs Playback に加え、**Cycle の STEP/CYCLE/AUTO** は別軸。 |
| Version | UR Dashboard `set/get/clear operational mode` は **5.0.0 / 5.6.0**（5.17 制限ではない）。 |
| Evidence | UR Dashboard e-Series 表。FANUC External Mode Select（モード制御源は一つ）。ABB IRC5 Product Manual 1.4。 |
| Unknown | UR 5.15.2 で Mode パスワード未設定時、PolyScope に Manual アイコンが出るかは人間確認待ち。 |
| Conflict | UR の Automatic は Remote ではない。KUKA AUT は外部制御なし、EXT が外部。 |

### power_state

| 項目 | 内容 |
|------|------|
| Common Concept | 電源投入、Servo/Motors On、ブレーキ解除は、プログラム実行より前の別遷移。 |
| Vendor-specific | UR: `robotmode` POWER_OFF / POWER_ON / IDLE / RUNNING + `brake release`。Yaskawa: Servo On（Remote では外部回路が必要な場合あり）。ABB: Motors On。KUKA: `$DRIVES_ON`。FANUC: IMSTP/Enable とサーボ。 |
| Evidence | UR Dashboard `robotmode` / `power on` / `brake release`（5.0.0、多くは Only Remote Control）。J-1 実測 `POWER_OFF`。 |
| Unknown | URSim で Power On 後の 3D 表示は J-2 未実施。 |

### safety_state

| 項目 | 内容 |
|------|------|
| Common Concept | Emergency Stop / Protective Stop / Fault は Program Stop とは別。復帰は Reset を要するのが一般的。 |
| Vendor-specific | UR: `safetymode`。FANUC: Fault + UI Fault Reset + DCS。ABB: E-Stop / Protective / enabling device。KUKA: `$CONF_MESS` 等。 |
| Evidence | ISO 10218-1:2011 停止機能。UR Dashboard `safetymode`。 |
| Unknown | 本 URSim セッションでの Protective Stop 遷移は未実測。 |

### program_state

| 項目 | 内容 |
|------|------|
| Common Concept | 未選択 / ロード済 / 実行中 / 一時停止 / 停止 / 完了 / 中断。 |
| Vendor-specific | UR: `programstate` PLAYING / PAUSED / STOPPED。FANUC: UO Program Running / Paused + Abort。ABB: RAPID 実行 + Program Pointer。Yaskawa: Job 選択 + StartJob。KUKA: プログラム選択 + CELL.SRC。 |
| Evidence | UR Dashboard。J-1: `STOPPED`。Phase I-Live: Secondary 送信後も STOPPED のまま。 |
| Conflict | Dashboard `load` 受理 ≠ PolyScope に Program が表示され実行された。 |

### execution_mode / cycle_model

| 項目 | 内容 |
|------|------|
| Common Concept | **プログラム内ループ**と **Controller が 1 Cycle として扱う繰り返し**は別層。連続 / N 回 / 外部トリガも別。 |
| Vendor-specific | Yaskawa: `SetCycleMode` STEP / CYCLE / AUTO（公式 YMConnect）。FANUC: UI Start / Prod Start / Cycle Stop。ABB: Run mode continuous vs cycle + `StartAtMain`。KUKA: CELL.SRC ループ + `$EXT_START` + PGNO。UR: Dashboard に Cycle 回数コマンドは見当たらない。繰り返しは URScript ループか、外部が `play` を繰り返す。 |
| Evidence | Yaskawa YMConnect ControlCommands。FANUC UOP。KUKA EXT シーケンス。 |
| Unknown | UR 5.15.2 に Controller 公式の counted cycle があるかは未確認（Dashboard 表には無い）。 |

### simulation_state

| 項目 | 内容 |
|------|------|
| Common Concept | シミュレーションと実機は別。実機接続はこのプロジェクトでは禁止。 |
| Vendor-specific | UR: PolyScope シミュレーション トグル。ログ上は `set real` / simulation。他社は Roboguide / RobotStudio / Office 等。 |
| Evidence | Phase I 起動ログ `set real`。2026-08-30 PolyScope 観測: シミュレーション ON、電源オフ。 |
| Unknown | トグルが人間操作かイメージ初期化後の変化かは、J-2 手順としては未完了。 |

### controller_state

UR `robotmode`: NO_CONTROLLER, DISCONNECTED, CONFIRM_SAFETY, BOOTING, POWER_OFF, POWER_ON, IDLE, BACKDRIVE, RUNNING。これは program_state でも control_authority でもない。

### transport_state

接続 / 切断 / タイムアウト。**所有権を持たない。** J-1: ESTABLISHED クライアントなしでも operational mode は AUTOMATIC のまま。

### operational_mode_source（UR 実測で追加した軸）

| 項目 | 内容 |
|------|------|
| Common Concept | 「今のモード」と「誰がそのモード切替権を持つか」は別。FANUC External Mode Select「モード制御源は一つ」に近い。 |
| Vendor-specific | UR Dashboard `set operational mode` 後、PolyScope から Manual/Automatic 変更不可。`clear operational mode` で返還。 |
| Evidence | 公式 Dashboard 表 5.0.0。J-1 実測: AUTOMATIC → clear → NONE。Forum: 切断だけでは戻らない。 |
| Conflict | Remote Control の Local/Remote とは別ロック。 |

---

## 2. UR 5.15.2 Mapping

| Facet | 5.15.2 での現れ | 調べ方 | 5.17+ を混ぜないこと |
|-------|-----------------|--------|----------------------|
| transport | Dashboard :29999 都度 connect/close | `live_ursim_manager._dashboard_command` | — |
| control_authority | Local / Remote。Settings → System → Remote Control → **Enable は切替ではない** | `is in remote control`。GUI Enable は人間 | 5.17 System 全面 Admin ロックは未使用 |
| operational_mode | MANUAL / AUTOMATIC / NONE | `get operational mode` | コマンド自体は 5.0.0 |
| operational_mode_source | Dashboard 所有 vs PolyScope | `set` / `clear operational mode` | — |
| power | POWER_OFF 等、brake release | `robotmode` | play/power の多くは Only Remote Control |
| program | STOPPED / PLAYING / PAUSED | `programstate`, `running` | — |
| simulation | ヘッダ右下トグル | GUI。Dashboard に専用コマンドなし（本調査範囲） | — |
| safety | `safetymode` | Dashboard | — |

公式 Remote Control（SW5_20、5.15 前後で同一記述）:

- Enable しても PolyScope は有効のまま。**すぐ Remote にはならない。**
- プロファイルで Remote を選んで初めて外部制御。
- Local ではネットワークからの power/load/play 相当を拒否。
- Remote では Move タブ移動、ペンダントからの Start/Load、Freedrive を拒否。
- Remote 中も状態監視は可。Remote のまま電源オフすると起動も Remote。

Dashboard から Local→Remote への切替は公式・Forum とも **安全上不可**（ISO の単一制御点）。

---

## 3. J-1〜J-9 実測結果

推測で PASS にしない。

| Phase | 状態 | 記録 |
|-------|------|------|
| **J-1** | **PASS（Agent 側）** | TCP 非保持。占有は `set operational mode`。`clear` で NONE。JSON: `D:\AI-Agent-data\runs\ai_tool\20260830_phase_j1_clear_operational_mode.json` |
| **J-2** | **未完了 / 非PASS** | 2026-08-30 PolyScope: 実行タブ、プログラム `<名前なし>`、状態 停止、電源オフ、シミュレーション ON、Play 未確認、3D 動作未確認。人間の Wait/MoveJ/Play/Stop は未実施 |
| **J-3** | **調査のみ** | Enable ≠ Remote。Live Enable は J-2 PASS 後。パスワードは保存しない |
| **J-4** | **部分** | State D + モード所有権は実測。A Local での Dashboard 拒否、B Remote 許可、C 復帰は **未実測** |
| **J-5** | 未実施 | J-2 非PASS のため |
| **J-6** | I-Live 既知のみ | `.script` load unknown failure。`.urp` なし。受理 ≠ 実行 |
| **J-7** | 未実施 | Validator → Live 実行は接続しない |
| **J-8** | **SKIP** | J-2 非PASS。Remote Enable/選択/play は未実施 |
| **J-9** | **SKIP** | 証拠経路は仕様として定義。実行成功の実測なし |

J-2 チェックリスト（未完了）:

- 編集可能か: 未確認（画面上は未作成プログラム）
- Simulation 変更: トグルは ON に見える。人間が意図して変更したかの記録なし → 成功扱いにしない
- Robot Initialize: 電源オフのまま
- 最小 Program 作成: なし
- Play / 3D / Stop: なし

---

## 4. State Model

単一 enum に畳まない。タプルとして扱う。

```text
IndustrialRobotSnapshot =
  transport_state
  × control_authority
  × operational_mode
  × operational_mode_source   # UR で実測。他社は「モード切替源」
  × power_state
  × safety_state
  × program_state
  × execution_mode
  × simulation_state
  × observation[]             # 何を見たか。状態そのものではない
```

J-1 スナップショット（実測）:

| Facet | 解除前 | 解除後 |
|-------|--------|--------|
| transport | 都度切断 | 都度切断 |
| control_authority | Local（`is in remote control` false） | Local |
| operational_mode | AUTOMATIC | NONE |
| operational_mode_source | Dashboard | PolyScope（公式 clear） |
| power | POWER_OFF | POWER_OFF |
| program | STOPPED | STOPPED |

Remote は一度も true になっていない。Automatic ロックと Remote を混同すると誤診断する。

---

## 5. State Transition Model

### 何をすれば変わるか（根拠付き）

| 遷移 | 何が必要か | 何をしても足りないか |
|------|------------|----------------------|
| Dashboard が operational mode を握る | `set operational mode manual\|automatic` | TCP 切断 |
| PolyScope に mode 切替を返す | **公式** `clear operational mode` | プロセス停止、接続切断 |
| Local → Remote（UR） | GUI: Enable **かつ** プロファイルで Remote | Dashboard コマンド、Enable だけ |
| Remote → Local（UR） | プロファイルで Local。`set operational mode` は Remote を外し得るが clear と GUI が必要（Forum） | TCP 切断 |
| Program Stopped → Running（UR 公式） | 多くの play/load は **Only Remote Control** | Local のまま Dashboard play |
| Running → Protective Stop → Stopped | 安全イベント + Reset。Program Stop ボタンとは別 | 通信切断だけでは安全状態は分からない |
| Power Off → 実行 | power on → brake release → play（権限と Remote 条件つき） | programstate だけ見る |

### 人間介入

```text
Running
  → Human takes pendant / Local
  → External motion commands rejected (ISO / UR Local)
  → Manual (vendor-specific)
  → 再開は Resume か Restart か、PP 位置に依存（ABB 等）
```

UR 5.15.2 での Human 介入後の Resume は **未実測**。

### 通信切断

```text
Agent Execution
  → TCP close
  → transport = disconnected
  → control_authority / operational_mode_source は残ることがある  # J-1 実測
  → Human が PolyScope で操作できるかは残存ロック次第
```

---

## 6. Cycle Model

「10 回繰り返す Tool」を URScript `for` に直結しない。

```text
Layer 0  Program-level loop     言語の while/for（URScript, RAPID, KRL, INFORM, TP）
Layer 1  Controller cycle       1 本の Program/Job を 1 Cycle として扱う（Yaskawa CYCLE、FANUC cycle stop）
Layer 2  Continuous execution   Cycle 終了後に次 Cycle（Yaskawa AUTO、ABB continuous、KUKA CELL LOOP）
Layer 3  Counted execution      N 回（コントローラ設定 or PLC カウンタ。UR Dashboard には未確認）
Layer 4  External trigger       PLC/API/Dashboard が Cycle 開始（FANUC UI、KUKA EXT_START、UR play）
```

関係:

| 事象 | 推奨的な扱い |
|------|----------------|
| Pause | Cycle カウンタを保持するかはベンダー依存。Program pause ≠ cycle abort |
| Stop | Cycle 中断。再 start が先頭か途中かは別設定（FANUC Start vs Prod Start） |
| Fault | safety_state。Reset なしに次 Cycle を打たない |
| Resume | 中断点から。Restart はポインタ先頭（ABB StartAtMain） |
| Human intervention | Authority が Local に戻ると Layer 4 トリガは拒否され得る |

UR 5.15.2: Layer 4 は Dashboard `play`（Remote 条件）。Layer 0 はスクリプト。Layer 1–3 の第一級 API は本調査では未確認 → **Unknown**。繰り返し Tool は「どの層か」を要求仕様に書く。

---

## 7. Human / Agent Handoff Model

正常系（ドラフト、未実装）:

```text
Human Control
  → Agent Request
  → Observe snapshot (7 facets + mode source)
  → Acquire Control Authority only if Human が許可し Local 占有中でない
  → Agent Execution
  → Execution Complete は program_state + observation で判定（応答文字列ではない）
  → Ownership Release（UR: clear operational mode、Remote なら Local 復帰）
  → Human Review
```

異常系（J-1 を一般化）:

```text
Agent Execution → Fault または通信切断
  → Agent プロセス停止
  → Ownership が残る?   YES になり得る（J-1）
  → Human 操作可能?     残存ロック次第。TCP 切断では足りない
```

前提を禁止する: **TCP 切断 = 操作権解放**。

---

## 8. Capability Observation

既存 Capability で足りるものは REUSE。新規 Core は作らない。

| ID | 内容 | Existing | Decision |
|----|------|----------|----------|
| HUMAN_CONTROL_OWNERSHIP | Agent が Controller 状態を握ると、切断後も人間のペンダント操作を阻害し得る | J-1 実測。TDA Idea Preservation の型 | **RECORD** |
| Controller Ownership Guard | 操作前に authority / mode source / program / safety を確認 | 未実装。Dashboard 問い合わせは既存 Manager で可能 | **DEFER** |
| Ownership Release | 終了時に `clear operational mode` 等を明示 | 公式コマンド。Manager に恒常組み込みは未 | **DEFER** |
| Human Handoff | 解放 → Local → 人間確認要求 | 未 | **DEFER** |
| State Snapshot | 操作前後の Facet 記録 | ResearchRecord / 実験 JSON | **RECORD**（形式のみ。Core 化しない） |
| Cycle Controller | Program loop ではなく Controller Cycle | 他社には存在。UR 5.15.2 は Unknown | **DEFER** |
| 専用 IndustrialRobotControl Core | 上記を C3 モジュール化 | ResearchRecord + 本 Spec で保持可能 | **REJECT**（今は C3 不要） |

判定フロー（実施済）:

```text
Observation (J-1)
  → 上位概念 Control Authority / single point of control
  → Common（ISO）かつ Vendor-specific（UR set operational mode）
  → Existing: live_ursim_manager, ResearchRecord, CapabilityObservation
  → RECORD spec / DEFER guards / REJECT new C3
```

---

## 9. REUSE / RECORD / DEFER / EXPERIMENTAL / REJECT

| 判定 | 対象 |
|------|------|
| **REUSE** | `live_ursim_manager`（都度 Dashboard）。`ResearchRecord` / `CapabilityObservation` / `PreservedIdea`。ISO 10218-1:2011 概念。UR Dashboard 公式コマンド |
| **RECORD** | 本 Spec。HUMAN_CONTROL_OWNERSHIP。7 Facet。Cycle 層。Handoff 異常系。J-1 JSON |
| **DEFER** | Ownership Guard / Release / Handoff 実装。J-8 Live Remote。J-2 人間試験。Cycle Controller。他社実測 |
| **EXPERIMENTAL** | なし（新モジュール未作成） |
| **REJECT** | プロセス停止だけで占有解除。通信できた = 実行成功。5.17 仕様の 5.15.2 適用。Validator PASS = 安全。新 C3 Core。パスワード保存 |

---

## 10. Common Specification Draft

```text
IndustrialRobotControlModel
│
├─ control_authority      Local | Remote | ExternalController | TeachPendant
│                           # 同時に運動開始できる源は一つ
├─ operational_mode       Manual | Automatic | Teach | Run
│                           # ベンダーにより Remote と同一キーに畳まれる
├─ operational_mode_source  Pendant | ExternalInterface | Unset
│                           # UR J-1 で必須。切断では消えない
├─ power_state            Off | On | ServoOn | BrakeReleased
├─ safety_state           Normal | ProtectiveStop | EmergencyStop | Fault
├─ program_state          None | Selected | Loaded | Running | Paused
│                         | Stopped | Completed | Aborted
├─ execution_mode         SingleCycle | Continuous | Counted | ExternalTrigger
├─ simulation_state       Simulation | Real
├─ controller_state       vendor robotmode / equivalent
├─ transport_state        Connected | Disconnected | TimedOut
├─ transitions            公式コマンド / GUI / 安全イベントのみ。非公式 workaround 禁止
├─ cycle_model            Layer 0–4（プログラム ≠ コントローラ Cycle）
└─ human_handoff          Acquire → Execute → Observe → Release → Review
```

各フィールドの記入規則: **Common Concept / Vendor-specific / Version / Evidence / Unknown / Conflict** を分離する（本カタログの表形式）。

実行成功の証拠経路（J-9 定義。未実測）:

```text
Command
  → Dashboard/API response     (受理)
  → controller_state           (robotmode 等)
  → program_state              (PLAYING 等)
  → PolyScope observation      (人間 UI)
  → simulation/motion observation
```

一段でも欠ければ実行成功と書かない。

---

## 11. 今後の Tool 開発向け Research Record 形式

既存 `ResearchRecord`（`ai_tool/experimental/development_assistance/research_record.py`）を envelope として使う。**新 Database Core は作らない。**

Facet は拡張フィールド `facet_records[]` に入れる:

```text
facet_id, common_concept, vendor_mapping[], version, evidence[], unknown[], conflicts[]
```

Capability は既存 `CapabilityObservation`（decision: REUSE|RECORD|DEFER|EXPERIMENTAL|REJECT）。

新しいロボット Tool 要求が来たときの最低質問:

1. どの Facet を変えるつもりか
2. Control Authority は誰か
3. 繰り返しは Cycle の何層か
4. 終了時の Ownership Release は何か
5. 成功の Observation はどの証拠経路か

---

## C3 判定

**新規 C3 Core は作らない。**

理由: 概念は ISO + 各社公開仕様で共通化できる。UR 固有ロックは公式 1 コマンド。記録は ResearchRecord + Spec Draft で足りる。実装 Guard は J-2/J-8 実測後でも遅くない（DEFER）。Defensive Core Policy の C1（Record）に相当。C3 Experimental モジュールは過剰。
