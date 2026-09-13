"""GPU 基本状態の実測 Tool。固定値フォールバック禁止。"""

from tools.system.gpu.nvidia_smi import query_gpu_status


def get_gpu_status():
    """
    nvidia-smi から GPU 状態を取得する。
    失敗時は unknown / unavailable / error を返し、架空値は返さない。
    """
    result = query_gpu_status()
    return {
        "gpu": result.get("gpu"),
        "temperature": result.get("temperature"),
        "utilization": result.get("utilization"),
        "vram_used": result.get("vram_used"),
        "vram_total": result.get("vram_total"),
        "ok": result.get("ok"),
        "status": result.get("status"),
        "error": result.get("error"),
        "observation_source": "real",
        "source": result.get("source"),
    }
