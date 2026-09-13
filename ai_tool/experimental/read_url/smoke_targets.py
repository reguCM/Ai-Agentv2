"""Real public URL targets for read_url_text smoke tests (verified stable hosts)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ContentKind = Literal["html", "plain"]


@dataclass(frozen=True)
class RealWebSmokeTarget:
    case_id: str
    url: str
    content_kind: ContentKind
    description: str
    verified_note: str

    def to_dict(self) -> dict:
        return asdict(self)


# Selected 2026-08-28: public, auth-free, small, not robots-blocked for general GET.
REAL_WEB_SMOKE_TARGETS: tuple[RealWebSmokeTarget, ...] = (
    RealWebSmokeTarget(
        case_id="smoke_example_com",
        url="https://example.com/",
        content_kind="html",
        description="IANA reserved Example Domain (HTML)",
        verified_note="https://example.com/ returns 200 text/html (IANA documentation domain).",
    ),
    RealWebSmokeTarget(
        case_id="smoke_w3_robots_txt",
        url="https://www.w3.org/robots.txt",
        content_kind="plain",
        description="W3C robots.txt (plain text)",
        verified_note="https://www.w3.org/robots.txt returns 200 text/plain; standard test artifact.",
    ),
    RealWebSmokeTarget(
        case_id="smoke_iana_example",
        url="https://www.iana.org/domains/example",
        content_kind="html",
        description="IANA Example Domains documentation page",
        verified_note="https://www.iana.org/domains/example returns 200 text/html.",
    ),
)
