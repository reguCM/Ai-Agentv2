"""Context Monitor CLI: レガシーインポート・集計・ダッシュボード生成。"""
from __future__ import annotations

import argparse
import json

from tools.system.context_monitor import (
    import_legacy_verifications,
    import_p11_compare_evidence,
    write_dashboard,
    write_recalibration_status,
    write_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Context Monitor 管理 CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("import-legacy", help="P2-6～P2-8 verify.json をインポート")
    sub.add_parser("import-p11-evidence", help="P2-11 compare.json を strategy_evidence に取り込む")
    sub.add_parser("aggregate", help="summary.json を生成")
    sub.add_parser("recalibrate", help="recalibration_status.json を生成")
    sub.add_parser("dashboard", help="summary + recalibration + dashboard.html を生成")

    args = parser.parse_args()
    if args.command == "import-legacy":
        result = import_legacy_verifications(skip_existing=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "import-p11-evidence":
        result = import_p11_compare_evidence(skip_if_imported=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "aggregate":
        summary = write_summary()
        print(json.dumps({"total_observations": summary.get("total_observations")}, ensure_ascii=False))
    elif args.command == "recalibrate":
        status = write_recalibration_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.command == "dashboard":
        path = write_dashboard()
        print(str(path))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
