import importlib
import importlib.util
import platform
import shutil


MODULE_CANDIDATES = {
    "cpu": ("psutil", "platform"),
    "gpu": ("pynvml",),
    "memory": ("psutil", "platform"),
    "default": ("psutil", "platform"),
}

COMMAND_CANDIDATES = {
    "cpu": ("wmic", "powershell"),
    "gpu": ("nvidia-smi", "powershell"),
    "memory": ("wmic", "powershell"),
    "disk": ("wmic", "powershell"),
    "default": ("wmic", "powershell"),
}

PSUTIL_CPU_ATTRS = (
    "cpu_percent",
    "cpu_count",
    "cpu_freq",
    "cpu_times",
    "sensors_temperatures",
)


def probe_module(name):
    spec = importlib.util.find_spec(name)
    if spec is None:
        return {
            "name": name,
            "available": False,
            "error": "not found",
        }

    try:
        module = importlib.import_module(name)
    except Exception as exc:
        return {
            "name": name,
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    info = {
        "name": name,
        "available": True,
        "version": getattr(module, "__version__", None),
        "attrs": [],
        "samples": {},
    }

    if name == "psutil":
        for attr in PSUTIL_CPU_ATTRS:
            if hasattr(module, attr):
                info["attrs"].append(attr)
        if hasattr(module, "cpu_count"):
            info["samples"]["cpu_count"] = module.cpu_count()
        if hasattr(module, "cpu_percent"):
            info["samples"]["cpu_percent"] = module.cpu_percent(interval=0)

    return info


def probe_command(name):
    path = shutil.which(name)
    return {
        "name": name,
        "available": bool(path),
        "path": path,
    }


def collect_local_inventory(subcategory=None):
    key = subcategory if subcategory in MODULE_CANDIDATES else "default"
    modules = [probe_module(name) for name in MODULE_CANDIDATES[key]]
    commands = [probe_command(name) for name in COMMAND_CANDIDATES.get(key, ())]
    return {
        "platform": platform.system(),
        "modules": modules,
        "commands": commands,
    }


def compact_inventory(inventory):
    available_modules = [
        item["name"]
        for item in inventory.get("modules") or []
        if item.get("available")
    ]
    missing_modules = [
        item["name"]
        for item in inventory.get("modules") or []
        if not item.get("available")
    ]
    available_commands = [
        item["name"]
        for item in inventory.get("commands") or []
        if item.get("available")
    ]
    return {
        "platform": inventory.get("platform"),
        "available_modules": available_modules,
        "missing_modules": missing_modules,
        "available_commands": available_commands,
    }


def find_module(inventory, name):
    for item in inventory.get("modules") or []:
        if item.get("name") == name:
            return item
    return None
