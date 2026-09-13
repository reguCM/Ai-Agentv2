# URSim Live Environment Recovery — Phase I-R

**実行日:** 2026-08-30  
**判定:** `PENDING_USER_APPROVAL`（Live URSim 未起動 — 環境構築にユーザー承認が必要）  
**Production 変更:** 0 | **新規 C3:** 0  
**Run:** `runs/ai_tool/20260830_115321_ur_program_validator_phase_i_r/`

---

## 1. 目的

Phase I の `BLOCKED` を再評価し、**公式 URSim** を再現可能な形で利用できる経路を調査する。Docker を目的とせず、公式 Simulator を検証 Backend として使えるかが本質。

---

## 2. 最終判断

```text
Decision: PENDING_USER_APPROVAL
Live mode: False
Recommended (primary): B. WSL2 + Docker Desktop
Alternative (official): C. VirtualBox + Official URSim VM 5.15.2
```

**大規模な OS/仮想化変更はユーザー承認なしに実施していない。**

---

## 3. Official Web Research（Phase H/I を盲信しない）

| ソース | 内容 |
|--------|------|
| [Docker Hub ursim_e-series tags](https://hub.docker.com/r/universalrobots/ursim_e-series/tags) | 公式。`5.15`→URSim 5.15.2、`5.25`→5.25.2（layer metadata） |
| [UR ROS2 URSim Docker setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/ursim_docker.html) | 公式。`-p 5900:5900 -p 6080:6080`。LAN 露出注意 |
| [VirtualBox Installation Guide](https://www.universal-robots.com/download/manuals-e-seriesur-series/installation-guides/installation-of-ursim-through-virtualbox-en/) | 公式。Non-Linux VM **5.15.2** 明記 |
| [Non-Linux 5.25.2 Download](https://www.universal-robots.com/download/software-ur-series/simulator-non-linux/offline-simulator-ur-series-e-series-ur-sim-for-non-linux-5252/) | 公式。新しい VM パッケージ |
| [Dashboard Server](https://www.universal-robots.com/developer/communication-protocol/dashboard-server/) | 公式。:29999 |
| Primary/Secondary Client | 公式。:30001/:30002 — URScript 送信（Level-2 設計） |

---

## 4. Version 比較（勝手に最新へ変更しない）

| Version | Docker tag | VM | Catalog 整合 | 判定 |
|---------|------------|-----|--------------|------|
| **5.15.2** | `5.15` | 公式 VirtualBox 5.15.2 | **HIGH** — Phase H/I catalog | **推奨維持** |
| 5.25.2 | `5.25` | 公式 Non-Linux 5.25.2 | LOW — catalog 拡張必要 | 明示的 migration 決定まで保留 |

**選定 Version:** PolyScope **5.15.2** / Docker `universalrobots/ursim_e-series:5.15` / Robot `UR5`

---

## 5. Environment Matrix

| Environment | Official | Windows | Automation | Reproducibility | Risk | Feasibility（実測） |
|-------------|----------|---------|------------|-----------------|------|---------------------|
| A. Docker Desktop | Yes | 条件付き | High | High | Medium | **BLOCKED** — daemon 停止 |
| B. WSL2 + Docker | Yes | Yes | High | High | Medium | **NEEDS_USER_APPROVAL** — WSL 未導入 |
| C. VirtualBox + 公式 VM | Yes | Yes | Medium | High | Medium | **NOT_INSTALLED** — VBox なし |
| D. Linux native | Yes | No | Medium | High | Medium | **NEEDS_USER_APPROVAL** |

推測値は使用していない。Feasibility はホストプローブ結果に基づく。

---

## 6. ホスト再プローブ

| 項目 | 値 |
|------|-----|
| OS | Windows 10 |
| CPU | i5-12400, VirtualizationFirmwareEnabled=True |
| RAM | ~64 GB |
| Disk C: free | 十分（8GB+ VM 要件を満たす見込み） |
| Docker CLI | 23.0.5 |
| Docker Desktop | インストール済 |
| Docker daemon | **停止** (`com.docker.service` Stopped/Manual) |
| WSL | **未導入**（distro なし） |
| VirtualBox | **未インストール** |
| HypervisorPresent | False |

### Docker 復旧試行

- Docker Desktop 起動を試行 → **daemon 起動せず**
- WSL2 未導入のため Windows 上の Docker Desktop バックエンドが成立しない可能性が高い
- **WSL インストールはユーザー承認なしに実施せず**

---

## 7. Docker vs VirtualBox 比較（今回の検証目的向け）

| 軸 | WSL2 + Docker | VirtualBox + 公式 VM |
|----|---------------|----------------------|
| 公式性 | Official | Official |
| Windows 起動安定性 | 中 — WSL2 + reboot 必要 | 中 — VBox + VM import |
| Validator 比較の反復実行 | **High** — tag pin + API | Medium — UI 比重 |
| Automation (Level 2) | **実装済** — dashboard + :30002 | 可能だが未実装 |
| 永続 programs | volume mount | VM disk |
| 必要作業 | WSL2 install, reboot | VBox install, UR VM download |

**Validator ↔ Simulation 反復比較** という目的では **B（WSL2 + Docker）を第一推奨**。  
Docker が不適切/不可の場合の **公式代替は C（VirtualBox VM）** — 非公式 workaround ではない。

---

## 8. Simulation Fidelity

```text
Official Specification → Static Validator → Official URSim → Observation
```

stub は Development Loop 構造確認用。**公式 Simulator の代替として自作 Simulator は作らない。**

---

## 9. Live Test（stub fallback — live blocked）

| ID | Validator | URSim | Compare |
|----|-----------|-------|---------|
| I-R1 | PASS | PASS | expected |
| I-R2 | FAIL | FAIL | expected |
| I-R3 | FAIL | FAIL | expected |
| I-R4 | FAIL | FAIL | expected |
| I-R5 | FAIL | FAIL | expected |
| I-R6 | PASS | PASS | T7: **NOT_FOUND** |

**T7:** 自然 blind spot 未発見。Validator 完全 **ではない** — テストセット限界。

---

## 10. Automation Level

| Level | 状態 |
|-------|------|
| 0 | **現在** |
| 2 | コード実装済 — live 環境待ち |

---

## 11. Officiality Decision Factor（新評価軸）

| 区分 | 例 |
|------|-----|
| Official | UR Docker Hub, UR VirtualBox guide, UR ROS2 docs |
| Official-adjacent | ROS community launch scripts（未採用） |
| Community | 非公式 forum snippets |
| Self-built | Phase H stub |

**公式 ≠ 常に正しい** — 信頼性・再現性評価の Factor として RECORD。

---

## 12. ユーザー承認ゲート — 推奨アクション

### オプション B（第一推奨）: WSL2 + Docker Desktop

```text
1. wsl --install（管理者、reboot 可能性）
2. Docker Desktop 起動 → WSL2 backend 確認
3. docker pull universalrobots/ursim_e-series:5.15
4. python ai_tool/run_ur_program_validator_phase_i_r.py 再実行
```

**メリット:** Level-2 自動化実装済、catalog 5.15 整合、CI 向き  
**デメリット:** OS 機能変更、reboot、WSL 学習コスト

### オプション C（公式代替）: VirtualBox + URSim VM 5.15.2

```text
1. VirtualBox インストール（ユーザー承認）
2. UR サポートサイトから Non-Linux 5.15.2 VM ダウンロード
3. 公式 VirtualBox 手順で import
4. PolyScope UI で smoke test
5. Dashboard IP を live_ursim_manager に設定（手動/HITL）
```

**メリット:** WSL 不要、公式 Non-Linux 手順  
**デメリット:** 大容量 DL、自動化は Docker より低い

---

## 13. Capability Discovery

| Idea | Decision |
|------|----------|
| Officiality as Decision Factor | RECORD |
| Simulation Backend abstraction | DEFER |
| Sandbox Runner revival | REJECT |

---

## 14. Success Criteria R1–R12

| ID | 結果 |
|----|------|
| R1 環境再調査 | ✓ |
| R2 公式方式比較 | ✓ |
| R3 Docker 試行 | ✓（daemon 起動不可を記録） |
| R4 VirtualBox 代替 | ✓ |
| R5–R8 Live 起動/実行 | ✗ — blocked |
| R9 Validator 比較 | ✓（stub） |
| R10 T7 探索 | ✓ NOT_FOUND |
| R11 Level-2 | ✗ — live blocked |
| R12 Dev Loop Live | ✗ — skipped |

---

## 15. Production / Core

- Production 変更: **0**
- 新規 C3: **0**
- REUSE: Phase H validator, Phase I live adapter, environment_recovery.py

---

## 16. 成果物

```
ai_tool/experimental/ur_program_validator/
  environment_recovery.py   # Matrix, version compare, decision
  recovery_test_cases.py    # I-R1〜I-R6
  phase_i_r_harness.py

ai_tool/run_ur_program_validator_phase_i_r.py
tests/.../test_ur_program_validator_phase_i_r.py
```

---

## 17. 結論

Phase I-R は **Architecture Investigation を完了**し、Live URSim は **環境構築のユーザー承認待ち**で停止した。

- Docker だけで BLOCKED 終了 **していない** — 公式 VirtualBox VM 経路を調査・記録
- Version **5.15.2 を維持** — 5.25.x へ勝手に移行しない
- 次のアクションは **B または C のユーザー選択**

承認後、`run_ur_program_validator_phase_i_r.py` で Live smoke test → I-R1〜I-R6 live → Development Loop を再実行可能。
