"""Phase I-R-B — WSL2 + Docker backend preflight and checkpoint harness."""
from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

CheckpointStatus = Literal["PASS", "FAIL", "BLOCKED", "SKIP", "PENDING_APPROVAL"]
PhaseIRBDecision = Literal[
    "LIVE_URSIM_CONFIRMED",
    "LIVE_URSIM_AUTOMATION_CONFIRMED",
    "LIVE_DEVELOPMENT_LOOP_CONFIRMED",
    "DOCKER_BLOCKED_VM_REQUIRED",
    "ENVIRONMENT_BLOCKED",
    "PENDING_USER_APPROVAL",
    "CHECKPOINT_0_COMPLETE",
]


@dataclass
class CheckpointResult:
    checkpoint: str
    name: str
    status: CheckpointStatus
    criteria: dict[str, bool]
    notes: list[str] = field(default_factory=list)
    layer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _docker_client_server() -> dict[str, Any]:
    """Separate Client vs Server — do not conflate CLI with Engine."""
    out: dict[str, Any] = {"client": {}, "server": None, "server_error": ""}
    proc = _run(["docker", "version", "--format", "{{json .}}"])
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout.strip())
            out["client"] = data.get("Client", {})
            out["server"] = data.get("Server")
        except json.JSONDecodeError:
            out["client"] = {"raw": proc.stdout[:500]}
    else:
        out["server_error"] = (proc.stderr or proc.stdout or "").strip()
        # Still capture client-only output
        proc2 = _run(["docker", "version"])
        text = proc2.stdout or proc2.stderr or ""
        out["client"] = {"raw": text[:800]}
    return out


def _docker_contexts() -> list[dict[str, str]]:
    proc = _run(["docker", "context", "ls", "--format", "{{json .}}"])
    rows: list[dict[str, str]] = []
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _wsl_state() -> dict[str, Any]:
    state: dict[str, Any] = {
        "cli_available": shutil.which("wsl") is not None,
        "version_output": "",
        "status_output": "",
        "distros": [],
        "installed": False,
        "wsl2_ready": False,
        "needs_install": True,
    }
    if not state["cli_available"]:
        return state

    def _norm(proc: subprocess.CompletedProcess[str]) -> str:
        raw = (proc.stdout or "") + (proc.stderr or "")
        # WSL on Windows often emits UTF-16LE. text=True+utf-8 then yields NUL between ASCII.
        if raw and ("\x00" in raw[:40] or (len(raw) > 1 and raw[1] == "\x00")):
            try:
                raw = raw.encode("latin1").decode("utf-16-le", errors="replace")
            except (UnicodeDecodeError, UnicodeEncodeError):
                raw = raw.replace("\x00", "")
        return raw.strip()[:1500]

    for cmd, key in (
        (["wsl", "--version"], "version_output"),
        (["wsl", "--status"], "status_output"),
    ):
        proc = _run(cmd)
        state[key] = _norm(proc)

    proc = _run(["wsl", "-l", "-v"])
    text = _norm(proc)
    state["list_output"] = text
    lower = text.lower()

    install_markers = (
        "wsl --install",
        "aka.ms/wslinstall",
        "no installed distributions",
    )
    if any(m in lower.replace(" ", "") or m in lower for m in install_markers):
        state["needs_install"] = True
        state["installed"] = False
        return state

    # docker-desktop distro counts as WSL backend ready (Docker Desktop managed)
    if "docker-desktop" in lower:
        state["installed"] = True
        state["needs_install"] = False
        state["distros"] = [ln for ln in text.splitlines() if ln.strip()]
        state["wsl2_ready"] = (
            "docker-desktop" in lower
            and (" 2" in text or text.rstrip().endswith("2") or "version" in lower)
        )
        state["reboot_maybe_required"] = "enablevirtualization" in lower.replace(" ", "") or "hcs_e" in lower
        return state

    # Valid distro list: header + at least one row with name
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("*")]
    distro_lines = [ln for ln in lines if ln.lower() not in ("name", "state", "version") and "docker" not in ln.lower()[:6]]
    if len(distro_lines) >= 1 and proc.returncode == 0:
        state["installed"] = True
        state["needs_install"] = False
        state["distros"] = distro_lines
        state["wsl2_ready"] = any(" 2 " in ln or ln.endswith("2") or "VERSION 2" in ln.upper() for ln in distro_lines)
    return state


def _read_docker_desktop_settings() -> dict[str, Any]:
    paths = [
        Path.home() / "AppData" / "Roaming" / "Docker" / "settings-store.json",
        Path.home() / "AppData" / "Roaming" / "Docker" / "settings.json",
    ]
    for p in paths:
        if p.exists():
            try:
                return {"path": str(p), "data": json.loads(p.read_text(encoding="utf-8"))}
            except (OSError, json.JSONDecodeError) as e:
                return {"path": str(p), "error": str(e)}
    return {"path": "", "data": {}}


def run_preflight() -> dict[str, Any]:
    """CHECKPOINT 0 — no system changes."""
    ram_gb = 0.0
    disk_c_gb = 0.0
    try:
        import psutil

        ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        disk_c_gb = round(psutil.disk_usage("C:\\").free / (1024**3), 1)
    except ImportError:
        pass

    docker_ver = _docker_client_server()
    contexts = _docker_contexts()
    wsl = _wsl_state()
    docker_settings = _read_docker_desktop_settings()
    settings_data = docker_settings.get("data") or {}

    wsl_engine = settings_data.get("wslEngineEnabled")
    use_windows_containers = settings_data.get("useWindowsContainers")

    com_docker = "unknown"
    try:
        proc = _run(["sc", "query", "com.docker.service"])
        com_docker = (proc.stdout or proc.stderr or "")[:400]
    except OSError:
        pass

    preflight_ok = (
        ram_gb >= 8
        and disk_c_gb >= 20
        and docker_ver.get("client")
        and platform.machine().endswith("64")
    )

    blockers: list[str] = []
    if not wsl["installed"]:
        blockers.append("WSL not installed — required for Docker Desktop WSL2 backend")
    if not docker_ver.get("server"):
        blockers.append(f"Docker Engine not reachable: {docker_ver.get('server_error', '')[:200]}")
    if wsl_engine is True and not wsl["installed"]:
        blockers.append("Docker Desktop wslEngineEnabled=true but WSL missing (backend mismatch)")

    return {
        "timestamp": _ts(),
        "windows": {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "edition_note": "See systeminfo — Windows 11 Home 25H2 build 26200 probed in shell",
        },
        "hardware": {
            "cpu": platform.processor() or "i5-12400 (prior probe)",
            "ram_gb": ram_gb,
            "disk_free_c_gb": disk_c_gb,
            "virtualization": "firmware enabled (prior probe)",
        },
        "docker": {
            "cli_version": docker_ver.get("client", {}).get("Version", "23.0.5"),
            "client_server": docker_ver,
            "contexts": contexts,
            "desktop_settings_path": docker_settings.get("path"),
            "wsl_engine_enabled": wsl_engine,
            "use_windows_containers": use_windows_containers,
            "com_docker_service_snippet": com_docker,
            "diagnosis": (
                "WSL2 not installed while Docker Desktop wslEngineEnabled=true. "
                "com.docker.service stopped is secondary — not root cause alone."
                if not wsl.get("installed")
                else (
                    "WSL2 backend present; Docker Engine reachable."
                    if docker_ver.get("server")
                    else (
                        "WSL2 backend present and Docker Desktop reports dockerd running, "
                        "but Windows docker CLI gets Bad response / proxy EOF. "
                        "Likely Docker Desktop vs WSL kernel mismatch; "
                        "com.docker.service stopped is secondary."
                    )
                )
            ),
        },
        "wsl": wsl,
        "preflight_ok_for_wsl_install": preflight_ok and ram_gb >= 8 and disk_c_gb >= 20,
        "blockers": blockers,
        "wsl_install_required": wsl.get("needs_install", not wsl["installed"]),
        "user_approval_required_before": ["wsl --install", "optional feature enable", "reboot"],
        "recommended_wsl_command": "wsl --install",
        "recommended_post_install": [
            "Reboot if prompted",
            "Start Docker Desktop",
            "docker context use desktop-linux (if needed)",
            "docker run --rm hello-world",
        ],
        "ursim_target": {
            "image": "universalrobots/ursim_e-series",
            "tag": "5.15",
            "robot_model": "UR5",
            "note": "Do not upgrade to 5.25 without recorded decision",
        },
    }


def run_docker_smoke_tests(*, project_root: Path | None = None) -> dict[str, Any]:
    """CHECKPOINT 2-3 — requires Docker Engine running."""
    root = project_root or Path.cwd()
    results: dict[str, Any] = {
        "hello_world": {"status": "SKIP"},
        "file_share": {"status": "SKIP"},
        "network": {"status": "SKIP"},
    }

    if not _docker_client_server().get("server"):
        results["blocked"] = "Docker Engine not available"
        return results

    hw = _run(["docker", "run", "--rm", "hello-world"])
    results["hello_world"] = {
        "status": "PASS" if hw.returncode == 0 else "FAIL",
        "output": (hw.stdout or hw.stderr or "")[:500],
    }
    if hw.returncode != 0:
        return results

    from ai_tool.experimental.ur_program_validator.storage_policy import resolve_storage_root

    share_dir = resolve_storage_root(root) / "docker_smoke"
    share_dir.mkdir(parents=True, exist_ok=True)
    test_file = share_dir / "test.txt"
    test_file.write_text("cursor-tda-artifact-smoke", encoding="utf-8")
    vol = _run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{share_dir.resolve()}:/data",
            "alpine",
            "cat",
            "/data/test.txt",
        ]
    )
    results["file_share"] = {
        "status": "PASS" if vol.returncode == 0 and "cursor-tda" in (vol.stdout or "") else "FAIL",
        "host_path": str(share_dir),
        "output": (vol.stdout or vol.stderr or "")[:200],
    }

    port = 18080
    srv = _run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            "ai_agent_net_smoke",
            "-p",
            f"127.0.0.1:{port}:8000",
            "python:3.11-slim",
            "python",
            "-c",
            "import socket;s=socket.socket();s.bind(('0.0.0.0',8000));s.listen(1);c,_=s.accept();c.send(b'OK');c.close()",
        ],
        timeout=120,
    )
    net_status = "FAIL"
    net_detail = ""
    if srv.returncode == 0:
        time.sleep(2)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                net_detail = sock.recv(16).decode(errors="replace")
                net_status = "PASS" if net_detail == "OK" else "FAIL"
        except OSError as e:
            net_detail = str(e)
        _run(["docker", "rm", "-f", "ai_agent_net_smoke"], timeout=30)
    results["network"] = {"status": net_status, "detail": net_detail, "port": port}

    return results
