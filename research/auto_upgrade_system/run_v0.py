"""Compatibility alias. Canonical: research.test_improvement_loop.run_v0."""
from research.test_improvement_loop.run_v0 import *  # noqa: F401,F403
from research.test_improvement_loop.run_v0 import main

if __name__ == "__main__":
    raise SystemExit(main())
