"""
Phase C/D-0: 日本語 Safety Report（安全断定禁止・機械/LLM/Gate/Trusted Personal を分離表示）。
"""

from __future__ import annotations

from typing import Any


def build_japanese_safety_report(
    *,
    candidate: dict | None,
    compatibility: dict | None,
    safety: dict | None,
    llm_bundle: dict | None,
    gate: dict | None,
    trusted_personal: dict | None = None,
) -> dict[str, Any]:
    candidate = candidate or {}
    compatibility = compatibility or {}
    safety = safety or {}
    llm_bundle = llm_bundle or {}
    gate = gate or {}
    trusted_personal = trusted_personal or {}
    analysis = (llm_bundle.get("analysis") if isinstance(llm_bundle, dict) else None) or {}

    machine = str(safety.get("machine_assessed") or safety.get("status") or "unknown")
    command = candidate.get("command")
    args = list(candidate.get("args") or [])

    what = analysis.get("operation_summary_ja") or (
        f"コマンド `{command}` を引数 {args} で実行しようとする操作です。"
        if command
        else "操作内容を特定できていません。"
    )
    why = (
        str(candidate.get("purpose") or candidate.get("question") or "").strip()
        or "要求との対応はまだ機械的に確定していません。"
    )
    targets = list(candidate.get("targets") or [])
    if not targets and command:
        targets = [f"{command} {' '.join(str(a) for a in args)}".strip()]

    safe_reasons = []
    for code in safety.get("rationale_codes") or []:
        safe_reasons.append(f"機械根拠コード: {code}")
    for line in analysis.get("rationale_ja") or []:
        safe_reasons.append(f"LLM分析: {line}")
    if analysis.get("similar_known_ops"):
        safe_reasons.append(
            "LLMが類似するとした既知読取操作: "
            + ", ".join(analysis.get("similar_known_ops") or [])
        )
    if not safe_reasons:
        safe_reasons.append("安全性を積極的に支持する根拠は見つかっていません。")

    unknowns = []
    unknowns.append("機械判定では安全性を確認できていません。" if machine == "unknown" else "")
    for item in analysis.get("cannot_rule_out") or []:
        unknowns.append(f"否定できない副作用・リスク: {item}")
    for code in safety.get("rationale_codes") or []:
        if any(k in str(code) for k in ("unknown", "unparsed", "unapproved", "compound")):
            unknowns.append(f"機械が指摘した不明点: {code}")
    if llm_bundle.get("error"):
        unknowns.append(f"LLM分析エラー: {llm_bundle.get('error')}")
    if analysis.get("obfuscation_or_dynamic"):
        unknowns.append("難読化または動的生成の疑いがあります。")
    unknowns = [u for u in unknowns if u]
    if not unknowns and machine != "safe":
        unknowns.append("追加の確認事項が残っている可能性があります。")

    side_effects = list(
        dict.fromkeys(
            list(safety.get("side_effects") or [])
            + list(analysis.get("side_effects") or [])
        )
    )
    next_checks = []
    if machine == "unknown":
        next_checks.append("より単純な読取専用コマンドへ分解できるか確認する")
        next_checks.append("ネットワーク・書込・プロセス操作が本当に無いことを静的に確認する")
    if gate.get("decision") == "Block":
        next_checks.append("代替の既知 read-only 手段を再探索する")
    if not next_checks:
        next_checks.append("現状の判定結果を監査ログとして保存する")

    rev = trusted_personal.get("reversibility") or {}
    impact = trusted_personal.get("impact") or {}
    ext = trusted_personal.get("external_effects") or {}
    resource = trusted_personal.get("resource_assessment") or {}
    env_res = resource.get("environment_resources") or {}
    res_impact = resource.get("resource_impact") or {}
    runtime = resource.get("execution_runtime") or {}
    res_safety = resource.get("resource_safety") or {}
    tp_decision = trusted_personal.get("decision")
    tp_mode = trusted_personal.get("mode")

    restore_methods = rev.get("restore_mechanisms") or []
    targets_covered = rev.get("targets_covered", "unknown")
    uncovered = rev.get("uncovered_targets") or []

    net_read = ext.get("network_read", "unknown")
    net_write = ext.get("network_write", "unknown")

    tp_section_lines = [
        "■ Trusted Personal / 判断材料（Phase D-0）",
        f"- mode: {tp_mode or 'n/a'}",
        f"- policy decision: {tp_decision or 'n/a'}",
        f"- allow_execute: {trusted_personal.get('allow_execute')}",
        f"- 影響範囲 scope/breadth: {impact.get('scope', 'unknown')} / {impact.get('breadth', 'unknown')}",
        f"- 復元可能性: {rev.get('status', 'unknown')}",
        f"- 復元方法: {', '.join(restore_methods) if restore_methods else '未確認'}",
        f"- 今回の対象が復元対象か (targets_covered): {targets_covered}",
        f"- 復元対象外: {uncovered if uncovered else 'なし/未評価'}",
        f"- ネットワーク read: {net_read}",
        f"- ネットワーク write: {net_write}",
        f"- external_effects: {ext.get('effects') or []}",
        f"- 環境リソース観測: source={env_res.get('source', 'none')}, "
        f"disk_free_ratio={env_res.get('disk_free_ratio', 'unknown')}, "
        f"memory_available_bytes={env_res.get('memory_available_bytes', 'unknown')}",
        f"- 予想リソース消費: disk_growth={res_impact.get('disk_growth', 'unknown')}, "
        f"unbounded_execution={res_impact.get('unbounded_execution', 'unknown')}",
        f"- resource_safety（操作 Safety とは別軸）: {res_safety.get('status', 'unknown')}",
        f"- 実行時間見積: {runtime.get('duration_estimate', 'unknown')} "
        f"（長時間＝危険とはみなしません）",
        f"- 終了条件が静的に分かる: {runtime.get('termination_statically_known', 'unknown')}",
        f"- 無限実行の疑い: {runtime.get('infinite_loop_suspected', 'unknown')}",
        f"- 停止手段: {runtime.get('stop_means_available', 'unknown')}",
        f"- 子プロセス大量生成リスク: {runtime.get('child_process_fanout_risk', 'unknown')}",
        f"- Trusted Personal rationale: {trusted_personal.get('rationale_codes')}",
        "注記: ディスク空き率などの固定閾値は D-0 では適用しません。",
        "注記: resource unknown を safe とはみなしません。",
        "注記: Web の『安全』『危険』文言は Policy 根拠にしません。",
    ]

    report_text = "\n".join(
        [
            "【Safety Report（日本語）】",
            "注意: これは安全性の証明ではありません。"
            "機械的に安全性を確認できていない場合があり、"
            "LLMによる分析も安全性の証明にはなりません。",
            "",
            f"■ 何をする操作か\n{what}",
            "",
            f"■ なぜ必要か\n{why}",
            "",
            "■ 対象",
            *[f"- {t}" for t in targets],
            "",
            "■ 安全と推定される根拠（断定ではありません）",
            *[f"- {x}" for x in safe_reasons],
            "",
            "■ 不明な点 / 判断できない点",
            *[f"- {x}" for x in unknowns],
            "",
            f"■ 想定される副作用\n- " + ("、".join(side_effects) if side_effects else "不明"),
            f"■ 必要権限\n- {safety.get('privilege') or 'unknown'}",
            f"■ ネットワークアクセス（機械）\n- {safety.get('network_access') or 'unknown'}",
            f"■ ネットワーク read / write（Trusted Personal）\n"
            f"- read: {net_read} / write: {net_write}",
            "",
            f"■ 機械判定 (machine_assessed)\n- {machine}",
            f"■ Compatibility\n- {compatibility.get('status')}",
            f"■ LLM分析\n- 実施: {'はい' if llm_bundle.get('ok') or llm_bundle.get('error') else 'いいえ'}",
            f"- モデル/プロファイル: {llm_bundle.get('model_profile_id') or 'n/a'}",
            f"- read_only_likely: {analysis.get('read_only_likely')}",
            f"- cannot_rule_out: {analysis.get('cannot_rule_out')}",
            f"- 確信度: {analysis.get('confidence') or 'n/a'}",
            f"- エラー: {llm_bundle.get('error') or 'なし'}",
            "",
            f"■ Phase B/C 機械 Gate 判定\n- decision: {gate.get('decision')}",
            f"- allow_execute（自動実行）: {gate.get('allow_execute')}",
            f"- presentation_only（実験候補の提示のみ）: {gate.get('presentation_only')}",
            f"- rationale_codes: {gate.get('rationale_codes')}",
            "",
            *tp_section_lines,
            "",
            "■ 次に確認するとよいこと",
            *[f"- {x}" for x in next_checks],
            "",
            "注記: ExperimentCandidate は自動実行しません。Safety Report を人間の判断材料とします。",
            "注記: cannot_rule_out が空でも安全性の証明にはなりません。",
            "注記: 人間が承認しても machine_assessed および機械 Gate の結果は書き換えません。",
            "注記: 単純な可否確認だけを求める文面にはしません。"
            "上記の判断材料を読んでください。",
        ]
    )

    return {
        "phase": "kss-phase-d0" if trusted_personal else "kss-phase-c",
        "language": "ja",
        "title": "Safety Report",
        "disclaimer": (
            "機械的に安全性を確認できていない可能性があります。"
            "LLMによる分析であり、安全性の証明ではありません。"
            "『安全です』という断定はしません。"
            "環境リソースの固定閾値は Phase D-0 では適用しません。"
        ),
        "what_it_does": what,
        "why_needed": why,
        "targets": targets,
        "estimated_safe_reasons": safe_reasons,
        "unknowns": unknowns,
        "side_effects": side_effects,
        "required_privilege": safety.get("privilege") or "unknown",
        "network_access": safety.get("network_access") or "unknown",
        "network_read": net_read,
        "network_write": net_write,
        "impact": impact,
        "reversibility": rev,
        "resource_assessment": resource,
        "machine_assessed": machine,
        "compatibility_status": compatibility.get("status"),
        "llm_analysis_summary": {
            "ok": bool(llm_bundle.get("ok")),
            "model_profile_id": llm_bundle.get("model_profile_id"),
            "confidence": analysis.get("confidence"),
            "read_only_likely": analysis.get("read_only_likely"),
            "cannot_rule_out": analysis.get("cannot_rule_out"),
            "error": llm_bundle.get("error"),
        },
        "gate_decision": gate.get("decision"),
        "gate_allow_execute": gate.get("allow_execute"),
        "gate_rationale_codes": gate.get("rationale_codes"),
        "trusted_personal_decision": tp_decision,
        "trusted_personal_mode": tp_mode,
        "trusted_personal_rationale_codes": trusted_personal.get("rationale_codes"),
        "next_checks": next_checks,
        "report_text_ja": report_text,
        "assert_not_safety_proof": True,
    }
