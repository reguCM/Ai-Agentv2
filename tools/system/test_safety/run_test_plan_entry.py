"""Registry entry for run_test_plan — execution only via Chat orchestrator bridge."""


def run_test_plan_entry(**_kwargs: object) -> dict[str, object]:
    return {
        "ok": False,
        "status": "failure",
        "error": {
            "code": "orchestrator_bridge_required",
            "message": (
                "run_test_plan must be executed through the Chat orchestrator Test Safety bridge; "
                "direct tool invocation is not authoritative."
            ),
        },
    }
