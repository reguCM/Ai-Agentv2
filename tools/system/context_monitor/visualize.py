"""Context Monitor 簡易ダッシュボード（静的 HTML）。"""
from __future__ import annotations

import html
import json
from pathlib import Path

from tools.system.context_monitor.aggregate import write_summary
from tools.system.context_monitor.paths import DASHBOARD_HTML, RECALIBRATION_JSON, ensure_monitor_dir
from tools.system.context_monitor.recalibration import write_recalibration_status


def _row_cells(d: dict) -> str:
    return "".join(
        f"<td>{html.escape(str(v if v is not None else '-'))}</td>"
        for v in (
            d.get("observation_count"),
            d.get("success_rate"),
            d.get("timeout_rate"),
            d.get("avg_elapsed_ms"),
            d.get("avg_vram_free_before_mib"),
            d.get("evaluation_state"),
        )
    )


def render_dashboard_html(summary: dict, recal: dict) -> str:
    ctx_rows = ""
    for ctx, data in (summary.get("by_context_size") or {}).items():
        ctx_rows += f"<tr><td>{html.escape(str(ctx))}</td>{_row_cells(data)}</tr>\n"

    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in recal.get("reasons") or [])

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8"/>
  <title>Context Monitor Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
    th {{ background: #f5f5f5; }}
    .state {{ padding: 0.5rem 1rem; background: #eef; border-radius: 4px; }}
    .warn {{ background: #fff3cd; }}
  </style>
</head>
<body>
  <h1>Context Monitor Dashboard</h1>
  <p>Generated: {html.escape(summary.get('generated_at', ''))}</p>
  <p class="state">評価状態: {html.escape(summary.get('evaluation_state_label', ''))}
     （観測数: {summary.get('total_observations', 0)}）</p>

  <h2>Context 別比較</h2>
  <table>
    <tr>
      <th>Context</th><th>観測数</th><th>成功率</th><th>timeout率</th>
      <th>平均実行時間(ms)</th><th>平均VRAM空き(前, MiB)</th><th>評価状態</th>
    </tr>
    {ctx_rows}
  </table>

  <h2>再調整要求</h2>
  <p class="{'warn' if recal.get('recalibration_required') else 'state'}">
    Status: {html.escape(recal.get('status', ''))}<br/>
    {html.escape(recal.get('message', ''))}
  </p>
  <ul>{reasons}</ul>
  <p><small>{html.escape(recal.get('note', ''))}</small></p>
</body>
</html>
"""


def write_dashboard(*, path: Path | None = None) -> Path:
    ensure_monitor_dir()
    summary = write_summary()
    recal = write_recalibration_status()
    html_content = render_dashboard_html(summary, recal)
    target = path or DASHBOARD_HTML
    target.write_text(html_content, encoding="utf-8")
    return target
