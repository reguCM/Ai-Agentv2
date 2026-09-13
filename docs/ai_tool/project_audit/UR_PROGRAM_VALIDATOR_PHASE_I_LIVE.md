# Phase I-Live — Official URSim Development Loop

**実行日:** 2026-08-30  
**判定:** `LIVE_LOOP_PARTIAL`  
**Production 変更:** 0 | **新規 C3:** 0  
**Run:** `D:\AI-Agent-data\runs\ai_tool\20260830_152446_ur_program_validator_phase_i_live`  
**対象:** `universalrobots/ursim_e-series:5.15` / VERSION **5.15.2** / **UR5** / 実機未接続

---

## 判定

```text
LIVE_LOOP_PARTIAL
```

Requirement → TDA → catalog URScript → Static Validator → Live URSim 送信 → Observation → LLM 説明まで経路は走った。Live の「実行成功」は Secondary `:30002` のヒューリスティックであり、Dashboard `play` / 運動は未確認。

`LIVE_LOOP_CONFIRMED` にしない: load/play 失敗、Remote Control=false、運動未確認。  
`LIVE_LOOP_BLOCKED` にしない: コンテナ・Dashboard 5.15.2・PolyScope(noVNC)・Validator・TDA loop は実測できた。

---

## Stub のみだった結果 / 今回 Live で確認できた結果

| 項目 | Phase I stub | Phase I-Live |
|------|--------------|--------------|
| Docker URSim 5.15.2 | 未起動 BLOCKED | 稼働 `ai_agent_ursim_phase_i` |
| Dashboard :29999 | 文献のみ | version=5.15.2, UR5, robotmode=RUNNING |
| PolyScope | 未確認 | noVNC `/vnc_lite.html` で GUI 確認 |
| I-T1 Validator PASS | stub URSim PASS | Live 送信 PASS（運動未確認） |
| I-T2/T3/T5 FAIL | stub も FAIL | Live PASS ヒューリスティック |
| T7 RUNTIME_FAIL | stub のみ | Live 未使用。自然 REJECT 未検出 |
| Dev Loop | LOOP_COMPLETED (stub) | LOOP_COMPLETED attempt 1（Live 経路、確定観測なし） |

---

## 1. Live 接続

- Container: `universalrobots/ursim_e-series:5.15` / VERSION 5.15.2 / UR5
- Dashboard: robotmode RUNNING, safetymode NORMAL, programstate STOPPED, running false
- is in remote control: **false**（operational mode automatic 設定後も false）
- Ports 5900/6080/29999/30001/30002 OPEN
- Mount: `D:\AI-Agent-data\ursim\programs` → `/ursim/programs`
- `:6080/` は noVNC 一覧。PolyScope は `http://127.0.0.1:6080/vnc_lite.html`（Automatic / Simulation / Normal / Stopped を目視）
- `run_smoke_test` によるコンテナ再作成はしていない

---

## 2. 既存 Manager（再利用）

使用: `_dashboard_command`, `execute_urscript_live`, `validate_script`, `compare_results`, `run_ursim_stub`, `run_development_loop`, `_run_live_test`。新規 Core なし。

Dashboard 取得可: version, robot model, robotmode, safetymode, programstate, running, loaded program, remote control, operational mode, power on, brake release, load, play。  
非対応: help, popup, safety status。

実装しない（必要性のみ）: Remote Control + .urp load/play、RTDE、完全 headless PolyScope。

---

## 3–5. Fixture / 段階 / Blind Spot

| ID | Validator | Live* | Stub | Live compare | 一致 |
|----|-----------|-------|------|--------------|------|
| I-T1 valid | PASS | PASS* | PASS | expected | Yes |
| I-T2 foo_bar | FAIL | PASS* | FAIL | possible_over_validation | No |
| I-T3 引数不足 | FAIL | PASS* | FAIL | possible_over_validation | No |
| I-T4 括弧 | FAIL | FAIL | FAIL | expected | Yes |
| I-T5 legacy_move | FAIL | PASS* | FAIL | possible_over_validation | No |
| I-T6 探索 | PASS | PASS* | PASS | expected | Yes |
| I-R1 valid | PASS | PASS* | PASS | expected | Yes |
| I-R2 syntax | FAIL | PASS* | FAIL | possible_over_validation | No |
| I-R3 unknown | FAIL | FAIL | FAIL | expected | Yes |
| I-R6 movej+movel | PASS | PASS* | PASS | expected | Yes |
| L-OBS-TEXTMSG | FAIL | PASS* | PASS | possible_over_validation | Yes |
| L-OBS-SLEEP | PASS | PASS* | PASS | expected | Yes |
| L-OBS-DIGITAL | WARNING | PASS* | PASS | unknown | Yes |

\*Live PASS = Secondary 応答に error 文字列が無いこと。応答は URControl バイナリ。programstate は STOPPED のまま。

段階: 書き込み PASS → load .script unknown failure → load .urp not found → play Failed → Secondary 送信はソケット成功・運動未確認。

Blind Spot: Validator PASS×URSim 拒否は未検出。FAIL×Live PASS* が主差（観測チャネル不足）。textmsg は catalog 外。synthetic RUNTIME_FAIL は未使用。

---

## 6. Development Loop

最大 2 attempt。実際は 1 で LOOP_COMPLETED。catalog スクリプトのみ。LLM は説明役。無限ループなし。

---

## 7–8. Human Review / Capability

確認できた: 接続、Dashboard 状態、noVNC GUI、Validator、stub 比較、TDA loop、LLM 説明、Secondary 送信。  
未確認: .urp load、play、Remote Control、関節運動、RTDE、実機安全。  
実機不可: 安全 I/O なし。Live PASS ≠ 運動。本フェーズは URSim 検証であり自動運転ではない。

Capability（RECORD のみ、今は実装しない）: headless .urp、運動確認、catalog builtin 拡充。新 C3 = 0。

---

## 2 点評価

**Validator を実用 Tool として:** 静的プレフィルタとしては部分成立。シミュレーションオラクル・安全認証としては未成立。Validator ゲートと URSim 確定観測は分ける。

**検証環境を基盤として:** Docker 5.15.2 + D: disk + Dashboard + noVNC + programs マウントはラボとして再利用可。無人 CI には Remote Control / .urp / 運動確認が不足。Production には載せない。

---

## Production

agent.py / registry / 新規 C3: すべて 0。実機接続なし。
