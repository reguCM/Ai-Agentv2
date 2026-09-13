"""GPU 使用プロセスの実測 Tool。固定プロセス一覧フォールバック禁止。"""

from tools.system.gpu.nvidia_smi import query_gpu_processes


def get_gpu_processes():
    """
    nvidia-smi compute-apps から GPU プロセスを取得する。
    失敗時は空リスト + status/error。固定の ollama/python は返さない。
    """
    result = query_gpu_processes()
    # 後方互換: 成功時はプロセス list を主結果にしつつメタを付与した dict も返す
    # 既存呼び出しが list 期待の場合があるため、list を返すときはメタを失う。
    # Agent が事実と混同しないよう、常に構造化 dict を返す。
    return {
        "processes": list(result.get("processes") or []),
        "ok": result.get("ok"),
        "status": result.get("status"),
        "error": result.get("error"),
        "observation_source": "real",
        "source": result.get("source"),
    }
