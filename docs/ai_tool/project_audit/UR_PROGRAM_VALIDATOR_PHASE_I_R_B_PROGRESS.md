# Phase I-R-B — Progress Report

**更新:** 2026-08-30  
**判定:** Docker / URSim Live **到達**（`universalrobots/ursim_e-series:5.15`、VERSION **5.15.2**）  
**Production 変更:** 0

---

## 現在の実測

| 項目 | 実測 |
|------|------|
| WSL | **2.7.12.0** / Kernel **6.18.33.2-2** |
| Distro | `docker-desktop` — Running / VERSION 2 |
| Docker Desktop | **4.88.1**（Engine **29.7.2**） |
| Docker WSL disk | **`D:\DockerDesktopWSL`**（`docker_data.vhdx` ≈ 19.1 GB） |
| C: leftover VHDX | **0** |
| `hello-world` | PASS |
| 既存イメージ | 保持（hello-world / voicevox / auto-gpt / chatgpt-ui） |
| URSim image | `universalrobots/ursim_e-series:5.15`（2.04 GB、digest `sha256:9cb14c98…`） |
| コンテナ | `ai_agent_ursim_phase_i` Running |
| Dashboard `:29999` | `version` → **5.15.2** / `robotmode` → `POWER_OFF` |
| PolyScope web `:6080` | 疎通 |
| Robot | **UR5**（simulation） |

---

## CHECKPOINT 状態（環境）

| CP | 名称 | 状態 |
|----|------|------|
| 0 | Preflight | **PASS** |
| 1 | WSL2 ready | **PASS** |
| 2 | Docker ready | **PASS**（Engine 29.7.2） |
| 3 | Container ready | **PASS**（hello-world） |
| 4 | URSim ready | **PASS**（5.15.2 / UR5 / dashboard） |
| 5–7 | URScript / TDA Live | **未実行** — ハーネス未再走 |

---

## Storage Policy

| 項目 | 状態 |
|------|------|
| Artifact root | `D:\AI-Agent-data` |
| Docker WSL disk | **`D:\DockerDesktopWSL`**（公式 Settings Apply 相当。JSON 手編集なし） |
| C: free（after move） | **501.8 GB** |
| D: free（after move） | **270.1 GB** |

工場出荷リセット・イメージ削除・既存データ削除は未実施。

---

## 次のアクション

Phase I-Live 実証は実施済。判定 `LIVE_LOOP_PARTIAL`。詳細は `UR_PROGRAM_VALIDATOR_PHASE_I_LIVE.md`。

---

## Production

変更 **0**
