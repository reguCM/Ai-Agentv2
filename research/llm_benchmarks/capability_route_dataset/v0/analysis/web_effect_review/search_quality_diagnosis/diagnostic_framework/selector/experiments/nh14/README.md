# NH14 README

Real-log shadow + External Help Request (mechanical only, no LLM).

## Pipeline

```
masked_inputs → compression → observation slots → prefill → fingerprint
→ validator → shadow_gate (nh14 remap) → selector → external_help_request?
```

## Run

```bash
python run_nh14_real_log_shadow_external_help.py
```

Production unchanged. `auto_fix_allowed=false` always.
