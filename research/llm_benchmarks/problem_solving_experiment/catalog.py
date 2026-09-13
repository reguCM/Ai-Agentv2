"""実験で LLM に見せる Tool 一覧。FA Schema ではない。本番 Registry には載せない。"""

from research.llm_benchmarks.problem_solving_experiment import adapters

TOOLS = [
    {
        "name": "get_current_failure",
        "capability": "Failure情報",
        "origin": "experiment_wrapper",
        "description": "Current test failure snapshot: error, traceback, return_value, warnings, source if the session has them.",
        "parameters": {"type": "object", "properties": {}},
        "handler": adapters.get_current_failure,
    },
    {
        "name": "read_file",
        "capability": "File Read / Code Read",
        "origin": "existing_unregistered",
        "description": "Read a workspace text file. Optional 1-based offset and limit for nearby lines.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
        "handler": adapters.read_file,
    },
    {
        "name": "search_files",
        "capability": "Repository Search / Definition 代用",
        "origin": "existing_unregistered",
        "description": "Search workspace text for a string. Optional path and glob (example *.py).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string"},
                "glob": {"type": "string"},
            },
            "required": ["query"],
        },
        "handler": adapters.search_files,
    },
    {
        "name": "list_files",
        "capability": "Repository Search",
        "origin": "existing_unregistered",
        "description": "List workspace files. Optional path, recursive, glob.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
                "glob": {"type": "string"},
            },
        },
        "handler": adapters.list_files,
    },
    {
        "name": "search_web",
        "capability": "Web Search",
        "origin": "registry",
        "description": "Web search. Returns titles, snippets, URLs. Does not fetch page bodies.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
        "handler": adapters.search_web,
    },
    {
        "name": "read_url_text",
        "capability": "Web Search",
        "origin": "registry",
        "description": "Fetch text from a known HTTP(S) URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_bytes": {"type": "integer"},
                "timeout_seconds": {"type": "number"},
            },
            "required": ["url"],
        },
        "handler": adapters.read_url_text,
    },
    {
        "name": "read_pdf",
        "capability": "PDF Read",
        "origin": "experiment_new",
        "description": "Read text from a workspace PDF if a PDF library is installed. May return pdf_library_not_installed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "page": {"type": "integer"},
                "max_chars": {"type": "integer"},
            },
            "required": ["path"],
        },
        "handler": adapters.read_pdf,
    },
    {
        "name": "get_execution_environment",
        "capability": "Environment",
        "origin": "experiment_wrapper",
        "description": "Python version, platform, architecture, executable, VIRTUAL_ENV, cwd.",
        "parameters": {"type": "object", "properties": {}},
        "handler": adapters.get_execution_environment,
    },
    {
        "name": "get_gpu_status",
        "capability": "Environment / Process",
        "origin": "registry",
        "description": "GPU name, temperature, utilization, VRAM from nvidia-smi.",
        "parameters": {"type": "object", "properties": {}},
        "handler": adapters.get_gpu_status,
    },
    {
        "name": "get_gpu_processes",
        "capability": "Process / Runtime",
        "origin": "registry",
        "description": "Processes currently using the GPU.",
        "parameters": {"type": "object", "properties": {}},
        "handler": adapters.get_gpu_processes,
    },
    {
        "name": "experiment_test_source",
        "capability": "Test / Execute",
        "origin": "experiment_new",
        "description": "Run a candidate python source in a temp file. Does not write production tools or call apply_repair.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "function_name": {"type": "string"},
            },
            "required": ["source"],
        },
        "handler": adapters.experiment_test_source,
    },
    {
        "name": "read_git_diff",
        "capability": "Diff / Change",
        "origin": "existing_unregistered",
        "description": "Read-only git status and diff of the workspace.",
        "parameters": {"type": "object", "properties": {}},
        "handler": adapters.read_git_diff,
    },
    {
        "name": "request_human_help",
        "capability": "Human HELP",
        "origin": "experiment_new",
        "description": "Record that a human decision is required. Does not patch.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["reason"],
        },
        "handler": adapters.request_human_help,
    },
]


def by_name():
    return {item["name"]: item for item in TOOLS}


def llm_catalog_text():
    lines = []
    for item in TOOLS:
        props = (item.get("parameters") or {}).get("properties") or {}
        args = ", ".join(props.keys()) or "(none)"
        lines.append(f"- {item['name']}({args}): {item['description']}")
    return "\n".join(lines)
