"""Offline parsers and documentation-backed provider discovery descriptors."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


PROVIDER_CATALOGS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models_url": "https://openrouter.ai/api/v1/models",
        "schema": "openai",
        "auth_env": "OPENROUTER_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://openrouter.ai/docs/api-reference/list-available-models",
    },
    "kilo": {
        "base_url": "https://ai-gateway.kilo.ai/api/v1",
        "models_url": "https://ai-gateway.kilo.ai/api/v1/models",
        "schema": "openai",
        "auth_env": "KILO_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://kilo.ai/docs/gateway/api-reference",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models_url": "https://api.groq.com/openai/v1/models",
        "schema": "openai",
        "auth_env": "GROQ_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://console.groq.com/docs/models",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "models_url": "https://api.cerebras.ai/v1/models",
        "schema": "openai",
        "auth_env": "CEREBRAS_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://inference-docs.cerebras.ai/api-reference/models/list-models",
    },
    "google_ai_studio": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "schema": "gemini",
        "auth_env": "GOOGLE_AI_STUDIO_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://ai.google.dev/api/models",
    },
    "huggingface": {
        "base_url": "https://router.huggingface.co/v1",
        "models_url": "https://router.huggingface.co/v1/models",
        "schema": "openai",
        "auth_env": "HUGGINGFACE_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://huggingface.co/docs/inference-providers/hub-api",
    },
}
PRICE_FIELDS = {
    "prompt": "input_cost_per_token",
    "completion": "output_cost_per_token",
    "image": "input_cost_per_image",
    "request": "input_cost_per_query",
    "input_cache_read": "cache_read_input_token_cost",
    "input_cache_write": "cache_creation_input_token_cost",
}
MODES = {
    "chat",
    "responses",
    "completion",
    "embedding",
    "image_generation",
    "image_edit",
    "audio_transcription",
    "audio_speech",
    "video_generation",
    "moderation",
    "rerank",
    "search",
}


def _positive_integer(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def _openai_spec(provider: str, row: dict[str, Any]) -> dict[str, Any]:
    spec = {"litellm_provider": provider, "upstream_model": row["id"], "mode": "unknown"}
    prices = row.get("pricing")
    evidence = {
        "source": "provider-model-catalog",
        "availability": "listed",
        "reported_prices": prices if isinstance(prices, dict) else None,
    }
    spec["pricing_evidence"] = evidence
    if isinstance(prices, dict):
        for source, destination in PRICE_FIELDS.items():
            if source not in prices or type(prices[source]) not in (str, int, float):
                continue
            try:
                amount = Decimal(str(prices[source]))
            except InvalidOperation:
                continue
            if amount.is_finite() and amount >= 0:
                spec[destination] = float(amount)
    architecture = row.get("architecture", {})
    top = row.get("top_provider", {})
    if not isinstance(architecture, dict):
        architecture = {}
    if not isinstance(top, dict):
        top = {}
    inputs = architecture.get("input_modalities", [])
    outputs = architecture.get("output_modalities", [])
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        raise ValueError("Model modalities must be arrays")
    legacy_modes = {
        "text+image->text": "chat",
        "text->text": "chat",
        "text->image": "image_generation",
        "text->embedding": "embedding",
        "audio->text": "audio_transcription",
    }
    if row.get("mode") in MODES:
        spec["mode"] = row["mode"]
    elif architecture.get("modality") in legacy_modes:
        spec["mode"] = legacy_modes[architecture["modality"]]
    elif outputs == ["image"] and "text" in inputs:
        spec["mode"] = "image_generation"
    elif outputs == ["embedding"] and "text" in inputs:
        spec["mode"] = "embedding"
    elif outputs == ["text"] and inputs == ["audio"]:
        spec["mode"] = "audio_transcription"
    elif outputs == ["text"] and "text" in inputs:
        spec["mode"] = "chat"
    parameters = row.get("supported_parameters", [])
    if not isinstance(parameters, list) or not all(isinstance(value, str) for value in parameters):
        raise ValueError("Model supported_parameters must be a string array")
    for capability, parameter in (
        ("supports_function_calling", "tools"),
        ("supports_tool_choice", "tool_choice"),
        ("supports_response_schema", "structured_outputs"),
    ):
        if "supported_parameters" in row:
            spec[capability] = parameter in parameters
    if "image" in inputs or architecture.get("modality") == "text+image->text":
        spec["supports_vision"] = True
    if "audio" in inputs:
        spec["supports_audio_input"] = True
    context = (
        _positive_integer(top.get("context_length"))
        or _positive_integer(row.get("context_length"))
        or _positive_integer(row.get("context_window"))
    )
    output = _positive_integer(top.get("max_completion_tokens")) or _positive_integer(row.get("max_completion_tokens"))
    if context:
        spec["max_input_tokens"] = context
    if output:
        spec["max_output_tokens"] = output
    if type(row.get("mayTrainOnYourPrompts")) is bool:
        spec["may_train_on_prompts"] = row["mayTrainOnYourPrompts"]
    return spec


def parse_openai_models(
    provider: str, response: dict[str, Any], *, qualify_ids: bool = True
) -> dict[str, dict[str, Any]]:
    """Preserve structured metadata from an OpenAI-compatible models listing."""
    if not isinstance(response, dict) or response.get("links", {}).get("next"):
        raise ValueError("Complete model pagination before importing the snapshot")
    rows = response.get("data")
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Model response must contain a bounded array")
    if "total_count" in response:
        total = response["total_count"]
        if type(total) is not int or total != len(rows):
            raise ValueError("Model total_count must match the complete snapshot")
    result = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"].strip()
            or len(row["id"]) > 500
        ):
            raise ValueError("Model entries require exact string IDs")
        if row.get("active") is False:
            continue
        key = f"{provider}/{row['id']}" if qualify_ids else row["id"]
        if key in result:
            raise ValueError("Duplicate provider model ID")
        result[key] = _openai_spec(provider, row)
    return result


def parse_provider_models(
    provider: str, response: dict[str, Any], *, qualify_ids: bool = True
) -> dict[str, dict[str, Any]]:
    """Parse a saved provider response without inferring free account access."""
    if provider not in PROVIDER_CATALOGS or not isinstance(response, dict):
        raise ValueError("Unsupported provider or invalid response")
    google = PROVIDER_CATALOGS[provider]["schema"] == "gemini"
    if not google:
        return parse_openai_models(provider, response, qualify_ids=qualify_ids)
    if response.get("nextPageToken") or response.get("links", {}).get("next"):
        raise ValueError("Complete provider pagination before importing the snapshot")
    rows = response.get("models" if google else "data")
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Model response must contain a bounded array")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Model entries must be objects")
        raw = row.get("name" if google else "id")
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 500:
            raise ValueError("Model entries require exact string IDs")
        if google:
            if not raw.startswith("models/"):
                raise ValueError("Gemini model names must use the documented resource prefix")
            raw = raw.removeprefix("models/")
            spec = {
                "litellm_provider": provider,
                "upstream_model": raw,
                "pricing_evidence": {
                    "source": "provider-model-catalog",
                    "availability": "listed",
                    "reported_prices": None,
                },
            }
            for source, destination in (
                ("inputTokenLimit", "max_input_tokens"),
                ("outputTokenLimit", "max_output_tokens"),
            ):
                if _positive_integer(row.get(source)):
                    spec[destination] = row[source]
            methods = row.get("supportedGenerationMethods", [])
            if not isinstance(methods, list) or not all(isinstance(value, str) for value in methods):
                raise ValueError("Gemini generation methods must be a string array")
            spec["supported_generation_methods"] = methods
        else:
            spec = _openai_spec(provider, row)
        key = f"{provider}/{raw}" if qualify_ids else raw
        if key in result:
            raise ValueError("Duplicate provider model ID")
        result[key] = spec
    return result


def main():
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(PROVIDER_CATALOGS), required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def deny_network(event, _args):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            raise RuntimeError("Provider snapshot parsing is offline")

    sys.addaudithook(deny_network)
    with args.snapshot.open("rb") as source:
        raw = source.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Snapshot exceeds the input size limit")
    result = parse_provider_models(args.provider, json.loads(raw))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"Parsed {len(result)} provider model records")


if __name__ == "__main__":
    main()
