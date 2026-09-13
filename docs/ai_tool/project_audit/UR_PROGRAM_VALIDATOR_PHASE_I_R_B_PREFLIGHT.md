# Phase I-R-B — WSL2 + Docker Preflight Report

**実行日:** 2026-08-30  
**Checkpoint:** `CHECKPOINT 0` 完了 → **`PENDING_USER_APPROVAL`**  
**Production 変更:** 0

---

## 1. 目的

公式 URSim を Live Backend として使うため、WSL2 + Docker Desktop 経路の **Preflight** を実施。  
`wsl --install` は **ユーザー承認前に実行していない**。

---

## 2. CHECKPOINT 0 — Preflight 結果

### Windows / Hardware（実測）

| 項目 | 値 |
|------|-----|
| OS | Windows 11 Home 25H2（build **26200**） |
| Architecture | AMD64 |
| CPU | 12th Gen Intel Core i5-12400 |
| RAM | **63.7 GB** ✓（要件 8GB+） |
| Disk C: free | **375 GB** ✓ |
| CPU 仮想化 (firmware) | 有効 |
| Hyper-V 要件 | VM モニター拡張: はい |

### Docker — Client / Server 分離

| 層 | 状態 |
|----|------|
| **Client** | Docker 23.0.5 ✓ |
| **Server (Engine)** | **✗ 未接続** |
| Context `default` | `npipe:////./pipe/docker_engine` |
| Context `desktop-linux` | `npipe:////./pipe/dockerDesktopLinuxEngine` |

**Server エラー:**

```text
open //./pipe/docker_engine: The system cannot find the file specified.
```

### Docker Desktop 設定（`settings.json` 実測）

| 設定 | 値 |
|------|-----|
| `wslEngineEnabled` | **true** |
| `useWindowsContainers` | false（Linux containers 想定） |
| `integratedWslDistros` | **[]**（WSL distro 未統合） |
| Memory | 2048 MiB |
| CPUs | 6 |

### com.docker.service

| 状態 | 値 |
|------|-----|
| STATE | STOPPED (1077) |

**診断（service だけを原因としない）:**

Docker Desktop ログより:

```text
wslEngineEnabled = true
useWindowsContainers = false
serviceIsRunning = false
```

→ **根本原因は WSL2 backend 未整備 + Engine 未起動**。service 単体 start では解決しない設計。

### WSL（実測）

| 項目 | 状態 |
|------|------|
| `wsl.exe` | 存在 |
| `wsl --version` | **未インストール**（install 案内メッセージ） |
| `wsl -l -v` | distro **なし** |
| WSL2 ready | **false** |

---

## 3. Preflight 判定

| 項目 | 結果 |
|------|------|
| Preflight OK（WSL 導入可能） | **✓** RAM/ Disk / 64-bit |
| WSL 導入必要 | **✓** |
| Docker Engine | **BLOCKED**（WSL 待ち） |
| URSim | **未着手**（CHECKPOINT 4 以降） |

---

## 4. 推奨 Version（変更なし）

| 項目 | 値 |
|------|-----|
| URSim | **5.15.2**（Docker tag `5.15`） |
| Robot | **UR5**（catalog 整合） |
| 5.25.x | **保留** — migration 記録なし |

---

## 5. 承認後の実行手順（CHECKPOINT 1→7）

### ユーザー承認後（管理者 PowerShell）

```powershell
wsl --install
# 再起動（プロンプトに従う）
```

### 再起動後

```powershell
wsl --version
wsl -l -v          # VERSION 2 の distro 確認
# Docker Desktop 起動
docker context use desktop-linux   # 必要なら
docker info                        # Server セクション成功確認
docker run --rm hello-world
python ai_tool/run_ur_program_validator_phase_i_r_b.py --wsl-approved
```

### CHECKPOINT 順

```text
0 Preflight        ← 今ここ（完了）
1 WSL2 ready
2 Docker ready
3 Container smoke (hello-world / file / network)
4 URSim pull + PolyScope
5 URScript + Validator compare
6 Programmatic (Dashboard :29999 / Secondary :30002)
7 TDA Development Loop (Live)
```

---

## 6. 成果物

```
ai_tool/experimental/ur_program_validator/
  wsl_docker_backend.py      # Preflight + Docker smoke
  phase_i_r_b_harness.py     # Checkpoint orchestration

ai_tool/run_ur_program_validator_phase_i_r_b.py
tests/.../test_ur_program_validator_phase_i_r_b.py
runs/ai_tool/*_phase_i_r_b/preflight.json
```

---

## 7. リスク（承認時の確認事項）

- **再起動**が必要になる可能性
- **Windows Optional Features** 有効化（WSL / Virtual Machine Platform）
- Docker Desktop **WSL2 based engine** 使用（Windows containers ではない）
- 追加 Linux distro は **Docker 目的のみなら最小限**（Ubuntu は Cursor/CLI 連携用候補）

---

## 8. 次のアクション — **ユーザー承認が必要**

以下の実行を承認してください:

1. `wsl --install`（システム変更、再起動の可能性）
2. 再起動後 Docker Desktop 起動
3. Phase I-R-B checkpoint 1〜7 の自動再実行

**承認後、Cursor で「WSL2 導入を承認」と返信いただければ CHECKPOINT 1 以降を進めます。**

VirtualBox 公式 VM 経路は、Docker 経路が失敗した場合の **公式代替**として Phase I-R で既に記録済みです。
