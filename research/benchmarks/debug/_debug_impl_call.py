import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT
"""④本体と同じ proposal + research_result で Implementation を呼ぶ"""
import json
from tools.ai.tool_builder.implementation import create_tool_implementation
from tools.ai.llm.adapter import build_implement_messages
from tools.ai.state.task_state import TaskState
from tools.system.llm import chat
from tools.system.config import get_llm_profile
from research.llm_benchmarks.environment_benchmark import verified_environment

data = json.load(open(ROOT / "research" / "llm_benchmarks" / "research_implement_results.json", encoding="utf-8"))
run = data["runs"][-1]

proposal = run["proposal"]
research = run["pipeline"]["research"]
request = run["request"]
state = TaskState.from_payload(run["state"])

profile = get_llm_profile("deepseek_coder_v2_16b")
MODEL = profile["model"]

materials = create_tool_implementation(
    proposal,
    environment=verified_environment(),
    research_result=research,
    request=request,
)

print("=== MATERIALS KEYS ===")
print(list(materials.keys()))
print(f"target_path: {materials.get('target_path')}")
print(f"target_function: {materials.get('target_function')}")
print(f"usable_findings: {len((materials.get('research_result') or {}).get('usable_findings') or [])}")

messages = build_implement_messages(materials, state=state)
print(f"\n=== MESSAGES ({len(messages)}) ===")
for m in messages:
    role = m.get("role", "?")
    content = m.get("content", "")
    print(f"[{role}] {len(content)} chars")
    if role == "user":
        print(content[:500])
        print("...")

print("\n=== CALLING LLM ===")
response = chat(model=MODEL, messages=messages)
text = response.message.content
print(f"response length: {len(text)}")
print(text[:1000])
