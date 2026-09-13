# PolyScope 5.15.2 — Simulation / Remote Control が変わらない理由

**対象:** Docker `universalrobots/ursim_e-series:5.15` / VERSION 5.15.2 / UR5  
**設定ファイル編集・非公式回避:** 未実施  
**Production 変更:** 0

## 結論（分離）

| 現象 | 主な所属 | 根拠 |
|------|----------|------|
| Remote Control が最初から無効、ヘッダに Local/Remote が出ない | **PolyScope 5.15 仕様** | ネットワーク制御は default restricted。Settings → System → Remote Control で Enable してから、プロファイルで切替 |
| Automatic と Remote Control を混同しやすい | **PolyScope 5.15 仕様** | Automatic/Manual は Operational Mode。Remote/Local は別機能 |
| 起動直後が Real（シミュレーションOFF）+ Automatic | **本 Docker イメージの初期状態** | ログ `set real` / `Operational mode changed from DISABLED to AUTOMATIC` |
| Dashboard だけでは Remote にできない | **PolyScope 仕様 + Docker は GUI 操作が必要** | `is in remote control` = false。公式も PolyScope 上の Enable を要求 |
| 5.17 の「System 全面 Admin ロック / Security デフォルト制限」 | **5.15.2 には適用しない** | 5.17.x Release Notes の変更。5.15.2 の User Manuals は 5.15 |

Admin の工場出荷パスワードは公式に **`easybot`**。5.15.2 でパスワード変更を強制するのは 5.17 仕様なので、ここでは要求しない。
