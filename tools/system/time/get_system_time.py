"""ローカル日時の実測 Tool。固定値フォールバック禁止。"""

from __future__ import annotations

from datetime import datetime


def get_system_time() -> dict:
    """
    実行ホストのローカル現在時刻を返す。
    datetime / timezone / formatted を必ず含める。架空の時刻は返さない。
    """
    now = datetime.now().astimezone()
    tzinfo = now.tzinfo
    tz_key = getattr(tzinfo, "key", None) if tzinfo is not None else None
    tz_name = now.tzname()
    timezone = tz_key or tz_name or (str(tzinfo) if tzinfo is not None else "unknown")
    return {
        "datetime": now.isoformat(timespec="seconds"),
        "timezone": timezone,
        "formatted": now.strftime("%Y-%m-%d %H:%M:%S %z"),
        "ok": True,
        "status": "ok",
        "error": None,
        "observation_source": "real",
        "source": "datetime.now_astimezone",
    }
