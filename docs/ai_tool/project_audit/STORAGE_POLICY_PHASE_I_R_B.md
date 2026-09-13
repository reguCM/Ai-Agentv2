# Storage Policy — Phase I-R-B Baseline

**記録日:** 2026-08-30  
**方針:** C: 大容量回避 / D: 移動可能データ優先 / 公式手順のみ / 変更前後 Probe

---

## 1. ドライブ使用量（Baseline — 変更前）

| Drive | Total | Used | Free |
|-------|-------|------|------|
| **C:** | 1906.6 GB | ~1535 GB | **371.8 GB** |
| **D:** | 1907.7 GB | ~1637 GB | **270.8 GB** |

リポジトリ: `D:\AI-Agent`（既に D: 上）

---

## 2. 大容量配置マップ

| カテゴリ | 現在 | 推奨 | 移動 | 承認 |
|----------|------|------|------|------|
| Project runs / artifacts | `D:\AI-Agent\runs\...` | **`D:\AI-Agent-data\runs\...`** | ✓ | 不要 |
| URSim program mount | repo 配下 | **`D:\AI-Agent-data\ursim\programs`** | ✓ | 不要 |
| Docker smoke test files | repo 配下 | **`D:\AI-Agent-data\docker_smoke`** | ✓ | 不要 |
| Docker Desktop WSL disk | **`D:\DockerDesktopWSL`**（実施済） | **D:\DockerDesktopWSL** | ✓ | **承認済・実施済** |
| WSL user distros | `%LOCALAPPDATA%\wsl` | D:\WSL（新規のみ） | ✓ | 要承認 |
| Windows / WSL system | C: | **移動しない** | ✗ | — |

**実測:** Docker WSL on C: ≈ **17.79 GB**（移動前）→ 移動後 **`D:\DockerDesktopWSL`**（`docker_data.vhdx` ≈ 19.1 GB + `main\ext4.vhdx` ≈ 0.1 GB）。C: 側の旧ファイルは 0。

---

## 3. 公式配置方法（ジャンクション非推奨）

### Docker Desktop（images / containers / WSL disk）

1. PC 再起動後 Docker Desktop 起動
2. **Settings → Resources → Advanced → Disk image location**
3. `D:\DockerDesktopWSL` 等を指定 → **Apply & restart**

出典: [Docker Desktop WSL docs](https://docs.docker.com/desktop/features/wsl/) — default `%LOCALAPPDATA%\Docker\wsl`

**タイミング:** `docker pull universalrobots/ursim_e-series:5.15` **前** が理想

**戻し方:** 同 UI で C: デフォルトパスに再指定

### WSL 新規 distro（Ubuntu 等 — Docker 目的のみなら最小限）

```powershell
# .wslconfig（新規 distro の default path）
# C:\Users\<user>\.wslconfig
[general]
distributionInstallPath=D:\\WSL

# または install 時
wsl --install -d Ubuntu --location D:\WSL\Ubuntu
```

出典: [Microsoft Learn — wsl --install --location](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)

**注:** `docker-desktop` / `docker-desktop-data` は Docker Desktop が管理 — **Docker UI で移動**

### プロジェクト artifact（Experimental コード）

- 環境変数: `AI_AGENT_STORAGE_ROOT=D:\AI-Agent-data`
- モジュール: `storage_policy.resolve_storage_root()`
- Run 出力: `D:\AI-Agent-data\runs\ai_tool\`

---

## 4. URSim 5.15 容量見積もり

| 項目 | サイズ |
|------|--------|
| `ursim_e-series:5.15` image | ~927 MB（Docker Hub） |
| Docker WSL disk 増分 | layer + metadata |
| Program mount | 小（テキスト script） |

---

## 5. 承認が必要な変更（実施前）

### 項目 A: Docker Disk image → D: — **ユーザー承認済（2026-08-30）**

| | |
|---|---|
| **内容** | Docker Desktop WSL disk を D: へ |
| **承認** | **approve_d_before_pull** — URSim pull 前に実施 |
| **提案パス** | `D:\DockerDesktopWSL` |
| **実施タイミング** | **PC 再起動 → Docker Desktop 起動後 → `docker pull` 前** |
| **手順** | Settings → Resources → Advanced → Disk image location → Browse → `D:\DockerDesktopWSL` → Apply & restart |
| **戻し方** | 同 UI で `%LOCALAPPDATA%\Docker\wsl` 相当の default に戻す |

**現状:** **実施済（2026-08-30）** — Docker Desktop 公式 Settings API（GUI の Apply 相当: `vm.resources.wslDataFolder`）で移動。JSON 手編集・工場出荷リセット・イメージ削除は未実施。既存 4 イメージは保持。移動後 `hello-world` PASS → `ursim_e-series:5.15` pull。

### 項目 B: 追加 Ubuntu distro

**今回は不要** — Docker Desktop の WSL backend のみ使用。Cursor/CLI 連携が必要になった場合のみ `--location D:\WSL\...` で追加。

---

## 6. コード変更（Production 0）

- `storage_policy.py` — Probe / paths / approval パッケージ
- `live_ursim_manager.py` — URSim programs → `D:\AI-Agent-data\ursim\programs`
- `wsl_docker_backend.py` — docker smoke → `D:\AI-Agent-data\docker_smoke`
- `phase_i_r_b_harness.py` — storage_probe を checkpoint 結果に含める

---

## 7. 次のアクション順

```text
1. PC 再起動 — 実施済（WSL2 PASS）
2. Docker Desktop 4.88.1 / Engine 29.7.2 — 実施済
3. Docker Disk image → D:\DockerDesktopWSL — 実施済
4. docker info / hello-world — 実施済
5. docker pull universalrobots/ursim_e-series:5.15 — 実施済（VERSION=5.15.2）
6. URSim コンテナ起動 + Dashboard :29999 — 実施済
7. 次: python ai_tool/run_ur_program_validator_phase_i_r_b.py --wsl-approved
```

### After Probe（Disk 移動後・URSim pull 後）

| Drive | Free |
|-------|------|
| **C:** | **501.8 GB**（移動前 482.7 GB → +19.1 GB） |
| **D:** | **270.1 GB**（移動前 289.3 GB → −19.2 GB） |

---

## 8. 禁止事項（本 Policy）

- C: への URSim image / run artifact の意図的配置
- ジャンクション / symlink を第一選択にしない
- ユーザー承認なしの Docker disk 移動
- Windows system 領域の強制移動
