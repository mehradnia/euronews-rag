from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    provider: str


ALLOWED_MODELS: dict[str, ModelInfo] = {m.id: m for m in [
    # Meta — Llama 4
    ModelInfo("meta-llama/Llama-4-Scout-17B-16E-Instruct", "Llama 4 Scout", "Meta"),
    ModelInfo("meta-llama/Llama-4-Maverick-17B-128E-Instruct", "Llama 4 Maverick", "Meta"),

    # Qwen — Qwen 3
    ModelInfo("Qwen/Qwen3-235B-A22B-Instruct-2507", "Qwen 3 235B", "Alibaba"),
    ModelInfo("Qwen/Qwen3-32B", "Qwen 3 32B", "Alibaba"),

    # DeepSeek — V3
    ModelInfo("deepseek-ai/DeepSeek-V3", "DeepSeek V3", "DeepSeek"),

    # Google — Gemma 3
    ModelInfo("google/gemma-3-27b-it", "Gemma 3 27B", "Google"),

    # Mistral
    ModelInfo("mistralai/Mistral-7B-Instruct-v0.3", "Mistral 7B v0.3", "Mistral"),
]}

DEFAULT_MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"


def is_model_allowed(model_id: str) -> bool:
    return model_id in ALLOWED_MODELS
