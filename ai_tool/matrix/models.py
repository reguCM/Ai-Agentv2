"""再利用可能な Web 知識の 1 件。回答文ではない。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MatrixRecord:
    record_id: str
    entity: str
    attribute: str
    value: str
    source_url: str
    source_title: str
    observed_at: str
    provenance: str
    ingest_id: str
    query: str
    excerpt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
