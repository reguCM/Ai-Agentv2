import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
PIPELINE_PATH = CONFIG_DIR / "pipeline.yaml"
LLM_MODELS_PATH = CONFIG_DIR / "llm_models.yaml"

_pipeline = None
_llm_models = None


def _parse_scalar(text):
    text = text.strip()
    if not text or text in ("null", "~", "Null", "NULL"):
        return None
    if text in ("true", "True", "yes", "Yes"):
        return True
    if text in ("false", "False", "no", "No"):
        return False
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    if text in ("[]",):
        return []
    if text in ("{}",):
        return {}
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _strip_comment(line):
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index].rstrip()
    return line.rstrip()


def _parse_simple_yaml(text):
    prepared = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        prepared.append((indent, line.strip()))

    def parse_block(start, min_indent):
        mapping = {}
        sequence = []
        mode = None
        index = start

        while index < len(prepared):
            indent, content = prepared[index]
            if indent < min_indent:
                break
            if indent > min_indent and mode is None:
                break

            if content.startswith("- "):
                if mode == "mapping":
                    break
                mode = "sequence"
                item_text = content[2:].strip()
                next_indent = (
                    prepared[index + 1][0] if index + 1 < len(prepared) else None
                )
                if item_text and ":" in item_text and not item_text.startswith("{"):
                    key, _, rest = item_text.partition(":")
                    item = {key.strip(): _parse_scalar(rest) if rest.strip() else None}
                    if next_indent is not None and next_indent > indent:
                        nested, index = parse_block(index + 1, next_indent)
                        if isinstance(nested, dict):
                            item.update(nested)
                    else:
                        index += 1
                    sequence.append(item)
                    continue
                if not item_text:
                    if next_indent is not None and next_indent > indent:
                        nested, index = parse_block(index + 1, next_indent)
                        sequence.append(nested)
                    else:
                        sequence.append(None)
                        index += 1
                    continue
                sequence.append(_parse_scalar(item_text))
                index += 1
                continue

            if mode == "sequence":
                break

            mode = "mapping"
            key, _, rest = content.partition(":")
            key = key.strip()
            rest = rest.strip()
            next_indent = prepared[index + 1][0] if index + 1 < len(prepared) else None
            if rest:
                mapping[key] = _parse_scalar(rest)
                index += 1
                continue
            if next_indent is not None and next_indent > indent:
                nested, index = parse_block(index + 1, next_indent)
                mapping[key] = nested
            else:
                mapping[key] = None
                index += 1

        if mode == "sequence":
            return sequence, index
        return mapping, index

    value, _ = parse_block(0, prepared[0][0] if prepared else 0)
    return value


def load_yaml(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        return _parse_simple_yaml(text)
    return yaml.safe_load(text)


def load_pipeline(reload=False):
    global _pipeline
    if _pipeline is None or reload:
        _pipeline = load_yaml(PIPELINE_PATH) or {}
    return _pipeline


def load_llm_models(reload=False):
    global _llm_models
    if _llm_models is None or reload:
        _llm_models = load_yaml(LLM_MODELS_PATH) or {}
    return _llm_models


def active_model_id():
    override = os.environ.get("AI_AGENT_MODEL")
    if override:
        return override
    return load_pipeline().get("active_model")


STAGE_ENV = {
    "research": "AI_AGENT_RESEARCH_MODEL",
    "judge": "AI_AGENT_JUDGE_MODEL",
    "implement": "AI_AGENT_IMPLEMENT_MODEL",
}


def stage_model_id(stage=None):
    """工程別モデル。未指定なら active_model。本番パイプラインはまだ工程を分けない。"""
    if stage:
        env_name = STAGE_ENV.get(stage)
        if env_name:
            override = os.environ.get(env_name)
            if override:
                return override
        models = load_pipeline().get("stage_models") or {}
        if models.get(stage):
            return models[stage]
    return active_model_id()


def get_llm_profile(model_id=None):
    models = load_llm_models()
    model_id = model_id or active_model_id()
    if model_id not in models:
        raise KeyError(f"llm_models.yaml にプロファイルがありません: {model_id}")
    profile = dict(models[model_id])
    profile["id"] = model_id
    profile.setdefault("materials", {})
    return profile


def get_pipeline():
    return load_pipeline()
