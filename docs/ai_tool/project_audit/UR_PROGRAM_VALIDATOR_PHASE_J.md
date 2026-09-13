# Phase J — Human Control Ownership + Industrial Control Model

**日付:** 2026-08-30  
**URSim:** 5.15.2 / UR5 / Docker `ai_agent_ursim_phase_i`  
**Production 変更:** 0 | **新規 C3:** 0  

本編の概念カタログ・仕様ドラフト:

[INDUSTRIAL_ROBOT_CONTROL_MODEL.md](./INDUSTRIAL_ROBOT_CONTROL_MODEL.md)  
Research Record: [research_records/RR_INDUSTRIAL_ROBOT_CONTROL_MODEL.json](./research_records/RR_INDUSTRIAL_ROBOT_CONTROL_MODEL.json)

公式 Dashboard（コマンド列は 5.0.0/5.6.0。5.17 権限モデルは未使用）:

https://www.universal-robots.com/manuals/EN/HTML/SW5_24/Content/prod-dashboard/Dashboard_table.htm

Remote Control 説明は 5.15 世代に存在する SW5_20 を優先（SW5_15 HTML は 404）:

https://www.universal-robots.com/manuals/EN/HTML/SW5_20/Content/prod-usr-man/software/PolyScope/content/hamburger_menu_g5/System_remote_en.htm

---

## J-1 Human Control Recovery — PASS（Agent 側）

占有は TCP keep-alive ではなく **`set operational mode` による operational_mode_source**。  
公式 `clear operational mode` → `NONE`。Remote は false のまま。

記録: `D:\AI-Agent-data\runs\ai_tool\20260830_phase_j1_clear_operational_mode.json`

---

## J-2 Human Simulation Test — 未完了（非PASS）

推測で成功にしない。2026-08-30 PolyScope 観測:

- 実行タブ、プログラム `<名前なし>`、状態 停止
- 電源オフ
- シミュレーション トグルは ON に見える（人間が J-2 手順を完了した記録はない）
- Play / 3D 動作 / Stop は未確認

J-8 Remote Live Test は **J-2 非PASS のため未実施**。

PolyScope: http://127.0.0.1:6080/vnc.html?autoconnect=1

人間確認が残っている項目: 編集、Initialize、最小 Program、Play、3D、Stop。Remote はまだ触らない。

---

## J-3〜J-10 調査（Live Remote なし）

Control Authority を ISO 10218-1:2011 の single point of control として一般化。FANUC / Yaskawa / ABB / KUKA は概念の有無のみ確認。完全 API 比較はしない。

詳細は INDUSTRIAL_ROBOT_CONTROL_MODEL.md。
