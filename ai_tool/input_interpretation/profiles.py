from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class InterpretationProfile:
    profile_id: str
    adapter_ids: tuple[str, ...]
    description: str

PROFILES = {
    "baseline": InterpretationProfile("baseline", ("raw", "safe_normalizer"), "dependency-free baseline"),
    "japanese": InterpretationProfile("japanese", ("raw", "safe_normalizer", "sudachi"), "optional Japanese analysis"),
    "compression": InterpretationProfile("compression", ("raw", "safe_normalizer", "llmlingua"), "optional compression"),
    "all": InterpretationProfile("all", ("raw", "safe_normalizer", "sudachi", "llmlingua"), "all adapters"),
}

def get_profile(profile_id: str) -> InterpretationProfile:
    if profile_id not in PROFILES:
        raise ValueError(f"unknown interpretation profile: {profile_id}")
    return PROFILES[profile_id]
