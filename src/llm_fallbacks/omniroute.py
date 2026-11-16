"""Read and optionally sort OmniRoute's catalog without rewriting route IDs."""
from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen
from typing import Any


def get_omniroute_models(base_url: str | None = None, api_key: str | None = None) -> dict[str, dict[str, Any]]:
    base_url = (base_url or os.environ.get('OMNIROUTE_BASE_URL', '')).rstrip('/')
    if not base_url:
        raise ValueError('Set OMNIROUTE_BASE_URL or pass base_url.')
    if not base_url.endswith('/v1'):
        base_url += '/v1'
    api_key = api_key if api_key is not None else os.environ.get('OMNIROUTE_API_KEY', '')
    headers = {'Accept': 'application/json', 'User-Agent': 'llm-fallbacks/0.1'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    with urlopen(Request(base_url + '/models', headers=headers), timeout=30) as response:
        catalog = json.load(response)['data']
    return {entry['id']: dict(entry) for entry in catalog}


def sort_omniroute_models(models: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Rank catalog entries by advertised token price, then context size.

    Missing prices sort last. Configured combo target order and strategies remain
    owned by OmniRoute. This function only sorts the caller's catalog listing.
    """
    def key(item: tuple[str, dict[str, Any]]) -> tuple[float, int, str]:
        name, spec = item
        pricing = spec.get('pricing') or {}
        prompt = pricing.get('prompt', spec.get('input_cost_per_token'))
        completion = pricing.get('completion', spec.get('output_cost_per_token'))
        try:
            cost = float(prompt) + float(completion) if prompt is not None and completion is not None else float('inf')
        except (ValueError, TypeError):
            cost = float('inf')
        context = int(spec.get('context_length') or spec.get('max_input_tokens') or 0)
        return cost, -context, name
    return sorted(models.items(), key=key)


def as_model_specs(models: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Adapt capabilities for existing filters while preserving exact IDs and metadata."""
    result = {}
    for name, original in models.items():
        spec = dict(original)
        kind = spec.get('type', 'chat')
        spec['mode'] = {'image': 'image_generation', 'video': 'video_generation'}.get(kind, kind)
        spec['litellm_provider'] = spec.get('owned_by', '')
        spec['max_input_tokens'] = spec.get('max_input_tokens') or spec.get('context_length', 0)
        capabilities = spec.get('capabilities') or {}
        spec['supports_function_calling'] = capabilities.get('tool_calling', False)
        spec['supports_vision'] = capabilities.get('vision', False)
        result[name] = spec
    return result


if __name__ == '__main__':
    print(json.dumps(dict(sort_omniroute_models(get_omniroute_models())), indent=2))
