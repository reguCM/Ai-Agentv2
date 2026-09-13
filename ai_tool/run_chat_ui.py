#!/usr/bin/env python3
"""Local Agent Chat UI を起動する。Production Workflow は変更しない。"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.chat_interface.server import PORT, serve


def main() -> int:
    port = PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    serve(port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
