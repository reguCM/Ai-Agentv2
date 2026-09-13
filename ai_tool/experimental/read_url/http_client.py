from __future__ import annotations

import urllib.error
import urllib.request
from typing import Callable

from ai_tool.experimental.read_url.config import USER_AGENT
from ai_tool.experimental.read_url.ssrf import validate_url

FetchFn = Callable[..., tuple[int, dict[str, str], bytes, str | None]]


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoAutoRedirect())


def default_http_get(
    url: str,
    *,
    timeout_seconds: float,
    max_bytes: int,
    max_redirects: int,
) -> tuple[int, dict[str, str], bytes, str | None]:
    """
    Perform GET with manual redirect handling and size limit.
    Returns (status_code, headers_dict, body_bytes, final_url).
    """
    current = url
    for _redirect in range(max_redirects + 1):
        err_url, err = validate_url(current)
        if err:
            raise ValueError(err)
        assert err_url is not None
        req = urllib.request.Request(
            err_url,
            method="GET",
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with _OPENER.open(req, timeout=timeout_seconds) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.headers.items()}
                final = resp.geturl()
                if status in (301, 302, 303, 307, 308):
                    location = headers.get("location")
                    if not location:
                        raise ValueError("redirect missing Location header")
                    if _redirect >= max_redirects:
                        raise ValueError("redirect limit exceeded")
                    from urllib.parse import urljoin

                    current = urljoin(final, location)
                    continue
                body = resp.read(max_bytes + 1)
                return status, headers, body, final
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location") if exc.headers else None
                if not location:
                    raise ValueError("redirect missing Location header") from exc
                if _redirect >= max_redirects:
                    raise ValueError("redirect limit exceeded") from exc
                from urllib.parse import urljoin

                current = urljoin(exc.url, location)
                continue
            body = exc.read(max_bytes + 1) if exc.fp else b""
            return exc.code, dict(exc.headers or {}), body, exc.url
        except urllib.error.URLError as exc:
            reason = exc.reason
            if "timed out" in str(reason).lower():
                raise TimeoutError("timeout") from exc
            raise ConnectionError(f"connection failure: {reason}") from exc
    raise ValueError("redirect limit exceeded")
