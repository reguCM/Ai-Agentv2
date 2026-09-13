# Cognitive Layer Phase 1 — 実装メモ

**status:** implemented (sidecar only)  
**date:** 2026-08-26  
**制約:** Selector / Tool 実行 / GPT / auto_fix / KB・Selector 上書きには未接続

---

## 何をしたか

会話理解を追跡する **Cognitive State** を、`TaskState` のサイドカーとして生成・更新・可視化する。

| モジュール | 役割 |
|------------|------|
| `tools/ai/state/cognitive_state.py` | スキーマ・更新 API・Markdown 可視化 |
| `tools/ai/state/cognitive_fingerprint.py` | Fingerprint **候補**のみ（Selector 未呼出） |
| `tools/ai/state/cognitive_session.py` | `cognitive_sessions/<id>/` へ永続化 |
| `tools/ai/state/run_cognitive_phase1.py` | CLI: `init` / `update` / `show` / `confirm` |

永続先（既定）: リポジトリ直下 `cognitive_sessions/<session_id>/`

- `COGNITIVE_STATE.md` — 人間確認用
- `state.json` — 機械スナップショット
- `fingerprint_candidate.json` — 将来 Selector 入力候補（`selector.invoked: false`）
- `audit_full.json` / `LAST_CHANGE.md` — 更新追跡

---

## CLI 例

```bash
python -m tools.ai.state.run_cognitive_phase1 init --goal "search_web の handoff を整理したい" --hypothesis "stdout と LLM 受け渡しが怪しい"
python -m tools.ai.state.run_cognitive_phase1 show --session-id <id>
python -m tools.ai.state.run_cognitive_phase1 update --session-id <id> --evidence "agent.py messages.append を確認"
python -m tools.ai.state.run_cognitive_phase1 confirm --session-id <id> --reviewer you
# 任意: --root <dir> はサブコマンドの前後どちらでも可
```

---

## Agent オプトイン

環境変数 `AI_AGENT_COGNITIVE_PHASE1=1` のときのみ、Clarity 直後にサイドカーを書く。  
既定はオフ。Selector・Tool 実行は呼ばない。

---

## やらないこと（Phase 1 境界）

- `DiagnosticSelector.select` の呼び出し
- Tool / GPT / 大型 LLM の自動起動
- auto_fix
- knowledge_base / selector 本番・実験正本の上書き

---

## テスト

```bash
python -m unittest tests.test_cognitive_phase1 -v
```
