# Condition C — Mechanical Prefill

Reuse NH9 small Observation slots, then apply mechanical prefill from materials.

Prefill only marks confirmation slots (OBSERVED/NOT_OBSERVED/HIGH). It does not invent root causes.

Flow:
saved obs → mechanical prefill → mapping → high_slots → gate → selector (no Large)
Remaining HIGH / sparse insufficient → HUMAN_REVIEW.
