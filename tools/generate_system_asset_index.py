#!/usr/bin/env python3
"""Generate docs/SYSTEM_ASSET_INDEX.md from registry/project_assets.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "registry" / "project_assets.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "SYSTEM_ASSET_INDEX.md"

FRESHNESS_LABEL = {
    "VERIFIED": "VERIFIED",
    "POSSIBLY_STALE": "POSSIBLY_STALE",
    "STALE": "STALE",
    "UNKNOWN": "UNKNOWN",
}

CATEGORY_ORDER = [
    "Policy",
    "Project Rule",
    "Cursor Rule",
    "Adapter",
    "Registry",
    "Schema / Contract",
    "Skill",
    "Guard / Gate",
    "Runtime Guard",
    "Safety Rule",
    "Harness",
    "Index",
    "Audit",
]


def _load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def registry_content_digest(registry: dict) -> str:
    payload = json.dumps(registry.get("assets") or [], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fmt_list(items: list[str] | None) -> str:
    if not items:
        return "—"
    return ", ".join(f"`{item}`" for item in items)


def render_markdown(registry: dict) -> str:
    assets = list(registry.get("assets") or [])
    assets.sort(key=lambda row: (CATEGORY_ORDER.index(row["category"]) if row["category"] in CATEGORY_ORDER else 99, row["asset_id"]))
    digest = registry_content_digest(registry)
    lines: list[str] = [
        "# SYSTEM_ASSET_INDEX",
        "",
        "**Human-readable Asset Index** — 正本は `registry/project_assets.json` です。",
        "本ファイルは生成物です。手編集しないでください。更新は Registry を編集し、",
        "`python tools/generate_system_asset_index.py` を実行してください。",
        "",
        "Registry は「現在の Repository の絶対最新状態」ではなく、**最後に確認された状態と鮮度**を記録します。",
        "",
        f"**Registry digest:** `{digest}`  ",
        f"**Human view:** `{registry.get('human_view_path', 'docs/SYSTEM_ASSET_INDEX.md')}`  ",
        "",
        "作業再開時は本 Index と `docs/CURRENT_DEVELOPMENT_STATE.md` を参照する。",
        "記載と実態が矛盾したら、現在の Repository を優先する。",
        "",
        "---",
        "",
    ]

    by_category: dict[str, list[dict]] = {}
    for asset in assets:
        by_category.setdefault(asset["category"], []).append(asset)

    for category in CATEGORY_ORDER:
        group = by_category.get(category)
        if not group:
            continue
        lines.append(f"## {category}")
        lines.append("")
        for asset in group:
            ver = asset.get("verification") or {}
            freshness = FRESHNESS_LABEL.get(str(ver.get("freshness") or "UNKNOWN"), "UNKNOWN")
            lines.append(f"### {asset['name']} (`{asset['asset_id']}`)")
            lines.append("")
            lines.append("| 欄 | 値 |")
            lines.append("|---|---|")
            lines.append(f"| **Freshness** | **{freshness}** |")
            lines.append(f"| Category | {asset['category']} |")
            lines.append(f"| Scope | {_fmt_list(asset.get('scope'))} |")
            lines.append(f"| Status | {asset['status']} |")
            path = asset.get("path")
            lines.append(f"| Path | `{path}` |" if path else "| Path | — (repository 外または複数) |")
            lines.append(f"| Source of Truth | {asset['source_of_truth']} |")
            lines.append(f"| Consumers | {_fmt_list(asset.get('consumers'))} |")
            lines.append(f"| Enforcement | {asset['enforcement_level']} |")
            lines.append(f"| Related Tests | {_fmt_list(asset.get('related_tests'))} |")
            lines.append(f"| Last Verified | {ver.get('last_verified_at', '—')} |")
            lines.append(f"| Verified Revision | `{ver.get('verified_revision', '—')}` |")
            lines.append(f"| Verification Method | {ver.get('verification_method', '—')} |")
            if ver.get("stale_reason"):
                lines.append(f"| Stale Reason | {ver['stale_reason']} |")
            if asset.get("notes"):
                lines.append(f"| Notes | {asset['notes']} |")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("<!-- generated-from: registry/project_assets.json -->")
    lines.append(f"<!-- registry-assets-sha256: {digest} -->")
    lines.append("")
    return "\n".join(lines)


def generate(*, registry_path: Path = REGISTRY_PATH, output_path: Path = OUTPUT_PATH) -> str:
    registry = _load_registry(registry_path)
    text = render_markdown(registry)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate SYSTEM_ASSET_INDEX.md from project_assets registry")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true", help="Exit 1 if output would change")
    args = parser.parse_args(argv)

    registry = _load_registry(args.registry)
    rendered = render_markdown(registry)
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
        if current != rendered:
            print("SYSTEM_ASSET_INDEX.md is out of date; run generate_system_asset_index.py", file=sys.stderr)
            return 1
        print("SYSTEM_ASSET_INDEX.md is up to date")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
