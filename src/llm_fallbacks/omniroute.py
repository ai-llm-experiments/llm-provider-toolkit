#!/usr/bin/env python3
"""Generate reviewable OmniRoute combos from the catalog and verified access.

Run with ``python -m llm_fallbacks.omniroute --help``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20_000
ROUTES = {
    "text": ({"chat", "responses", "completion"}, "chat/completions"),
    "agent": ({"chat", "responses"}, "chat/completions"),
    "coding": ({"chat", "responses"}, "chat/completions"),
    "persona": ({"chat", "responses"}, "chat/completions"),
    "image": ({"image_generation"}, "images/generations"),
    "image-edit": ({"image_edit"}, "images/edits"),
    "embed": ({"embedding"}, "embeddings"),
    "transcribe": ({"audio_transcription"}, "audio/transcriptions"),
    "speech": ({"audio_speech", "speech"}, "audio/speech"),
    "video": ({"video_generation"}, "videos/generations"),
    "music": ({"music_generation"}, "music/generations"),
    "moderate": ({"moderation"}, "moderations"),
    "rerank": ({"rerank"}, "rerank"),
    "web-search": ({"search"}, "search"),
    "web-fetch": ({"web_fetch"}, "web/fetch"),
}


DYNAMIC_ROUTER_IDS = frozenset({
    "openrouter/free", "openrouter/auto", "openrouter/auto-code", "openrouter/auto-beta",
    "openrouter/pareto-code", "openrouter/fusion", "typesafe/jev-router", "nvidia/switchyard",
})
GATEWAY_PREFIXES = {"openrouter": "openrouter", "kilo": "kilo", "kilocode": "kilo",
                    "kilo-gateway": "kilo", "kg": "kilo", "kc": "kilo"}
CONTEXT_SUFFIX = re.compile(r"\[(\d+)([kKmM])?\]\s*$")


def is_exact_target(model: str) -> bool:
    return not any(character in model for character in ("*", "?", "#", "\\")) and not any(
        ord(character) < 32 or character.isspace() or character == "\ufeff" for character in model
    )


def is_dynamic_router(provider: str, model: str) -> bool:
    """Classify selector identity without rewriting the emitted exact model ID."""
    normalized = model.strip()
    # Native stripContextWindowSuffix removes a trailing [digits][k|m] tag.
    # Hold nested forms too because successive proxy/parser layers can strip it.
    while CONTEXT_SUFFIX.search(normalized):
        normalized = CONTEXT_SUFFIX.sub("", normalized).rstrip()
    normalized = "/".join(part.strip().strip("\ufeff").strip() for part in normalized.split("/"))
    normalized = normalized.split(":", 1)[0].strip()
    current_provider = GATEWAY_PREFIXES.get(provider, provider)
    while "/" in normalized:
        if normalized in DYNAMIC_ROUTER_IDS or normalized.startswith("kilo-auto/"):
            return True
        prefix, remainder = normalized.split("/", 1)
        gateway = GATEWAY_PREFIXES.get(prefix)
        if gateway is None:
            break
        current_provider = gateway
        normalized = remainder
    return f"{current_provider}/{normalized}" in DYNAMIC_ROUTER_IDS or normalized.startswith("kilo-auto/")


def read_json(path: Path):
    with path.open("rb") as source:
        raw = source.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"Input exceeds {MAX_INPUT_BYTES} bytes: {path.name}")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def moment(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps must include their UTC offset")
    return parsed.astimezone(timezone.utc)


def text(value, label: str, max_length: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"Invalid {label}")
    return value.strip()


def zero(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value == 0


def number(value, default=0):
    return value if type(value) in (int, float) and math.isfinite(value) else default


def has_evidence(value) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def generate(catalog, policy, as_of: datetime, catalog_hash: str, policy_hash: str):
    if not isinstance(catalog, list) or len(catalog) > MAX_ROWS:
        raise ValueError("Catalog must be a bounded free_models.json array")
    if not isinstance(policy, dict) or type(policy.get("version")) is not int or policy["version"] != 1:
        raise ValueError("Access policy version must be 1")
    attestations = policy.get("targets", [])
    if not isinstance(attestations, list) or len(attestations) > MAX_ROWS:
        raise ValueError("targets must be a bounded array")
    age_hours = policy.get("maxAgeHours", 24)
    if type(age_hours) not in (int, float) or not math.isfinite(age_hours) or age_hours <= 0:
        raise ValueError("maxAgeHours must be a positive finite number")
    supported = policy.get("comboEndpoints", [])
    if not isinstance(supported, list) or not all(isinstance(x, str) for x in supported):
        raise ValueError("comboEndpoints must list verified runtime endpoint paths")
    requested_attempts = policy.get("maxGlobalAttempts", 200)
    if type(requested_attempts) is not int or not 1 <= requested_attempts <= 200:
        raise ValueError("maxGlobalAttempts must be between 1 and 200")
    deadline_ms = policy.get("comboTimeoutMs", 600_000)
    if type(deadline_ms) is not int or not 1000 <= deadline_ms <= 2_147_483_647:
        raise ValueError("comboTimeoutMs must be an integer between 1000 and 2147483647")
    mappings = policy.get("providerMappings", [])
    if not isinstance(mappings, list) or len(mappings) > MAX_ROWS:
        raise ValueError("providerMappings must be a bounded array")
    provider_mappings = set()
    for mapping in mappings:
        if not isinstance(mapping, dict) or not has_evidence(mapping.get("evidence")):
            raise ValueError("Provider mappings require nonblank evidence references")
        provider_mappings.add((text(mapping.get("catalogProvider"), "mapping catalogProvider"),
                               text(mapping.get("providerId"), "mapping providerId")))
    index = {}
    catalog_rank = {}
    for rank, row in enumerate(catalog):
        if not isinstance(row, dict):
            raise ValueError("Catalog rows must be objects")
        identity = (text(row.get("provider"), "catalog provider"), text(row.get("id"), "catalog id"))
        if identity in index:
            raise ValueError(f"Duplicate catalog identity: {identity}")
        index[identity] = row
        catalog_rank[identity] = rank

    groups = defaultdict(list)
    group_endpoints = {}
    embedding_spaces = {}
    decisions = []
    seen = set()
    seen_runtime_targets = set()
    for target in attestations:
        if not isinstance(target, dict):
            raise ValueError("Target attestations must be objects")
        provider = text(target.get("catalogProvider"), "catalogProvider")
        model_id = text(target.get("catalogId"), "catalogId")
        node = text(target.get("providerId"), "providerId")
        model = text(target.get("model"), "upstream model")
        identity = (provider, model_id, node, model)
        if identity in seen:
            raise ValueError(f"Duplicate target: {identity}")
        seen.add(identity)
        runtime_identity = (node, model)
        if runtime_identity in seen_runtime_targets:
            raise ValueError(f"Duplicate runtime target: {runtime_identity}")
        seen_runtime_targets.add(runtime_identity)
        row = index.get((provider, model_id))
        reasons = []
        if not is_exact_target(model_id) or not is_exact_target(model):
            reasons.append("model-target-syntax-not-exact")
        if is_dynamic_router(provider, model_id) or is_dynamic_router(provider, model):
            reasons.append("dynamic-router-policy-unbounded")
        if model != model_id:
            reasons.append("upstream-model-differs-from-canonical-id")
        if node != provider and (provider, node) not in provider_mappings:
            reasons.append("provider-mapping-unverified")
        if row is None:
            reasons.append("absent-from-canonical-catalog")
        elif row.get("is_free") is not True or not all(zero(row.get(k)) for k in (
            "input_cost_per_token", "output_cost_per_token"
        )):
            reasons.append("catalog-does-not-declare-zero-token-prices")
        if target.get("connected") is not True:
            reasons.append("connection-unverified")
        if target.get("providerScopeApproved") is not True:
            reasons.append("all-provider-accounts-must-match-route-policy")
        prices = target.get("prices", {})
        if not isinstance(prices, dict) or not prices or not all(zero(v) for v in prices.values()):
            reasons.append("all-applicable-prices-must-be-explicit-zero")
        if target.get("pricesComplete") is not True:
            reasons.append("applicable-price-fields-unverified")
        if target.get("freeOnlyEnforced") is not True:
            reasons.append("paid-escalation-boundary-unverified")
        if target.get("requestSucceeded") is not True:
            reasons.append("live-request-unverified")
        observed = moment(text(target.get("verifiedAt"), "verifiedAt"))
        age = (as_of - observed).total_seconds() / 3600
        if age < 0 or age > age_hours:
            reasons.append("verification-outside-freshness-window")
        sources = target.get("evidence", [])
        if not has_evidence(sources):
            reasons.append("evidence-missing")
        privacy = target.get("privacy")
        if privacy not in ("private-approved", "public-demo"):
            reasons.append("privacy-unclassified")
        purposes = target.get("purposes", [])
        if not isinstance(purposes, list) or not purposes or any(x not in ROUTES for x in purposes):
            reasons.append("purpose-unclassified")
            purposes = []
        entry = {"catalogProvider": provider, "catalogId": model_id, "providerId": node,
                 "model": model, "catalogRank": catalog_rank.get((provider, model_id)),
                 "excluded": reasons, "routes": []}
        decisions.append(entry)
        if reasons:
            continue
        for purpose in sorted(set(purposes)):
            modes, endpoint = ROUTES[purpose]
            rejected = []
            if row.get("mode") not in modes:
                rejected.append("canonical-mode-incompatible")
            endpoints = target.get("endpoints", [])
            if not isinstance(endpoints, list) or not all(isinstance(x, str) for x in endpoints):
                raise ValueError("endpoints must list verified endpoint paths")
            if endpoint not in endpoints:
                rejected.append("endpoint-unverified")
            if endpoint not in supported:
                rejected.append("runtime-combo-dispatch-unverified")
            if purpose in ("agent", "coding") and (
                row.get("supports_function_calling") is not True or target.get("toolsVerified") is not True
            ):
                rejected.append("tool-contract-unverified")
            if purpose in ("coding", "persona"):
                suitability = target.get("purposeEvidence", {})
                proof = suitability.get(purpose) if isinstance(suitability, dict) else None
                if not isinstance(proof, str) or not proof.strip():
                    rejected.append("task-suitability-evidence-missing")
            suffix = "free" if privacy == "private-approved" else "free-demo"
            route_name = f"{purpose}-{suffix}"
            embedding_fingerprint = None
            if purpose == "embed":
                space = target.get("embeddingSpace")
                if (not isinstance(space, dict) or not isinstance(space.get("identity"), str)
                        or not space["identity"].strip() or len(space["identity"]) > 512
                        or type(space.get("dimensions")) is not int or space["dimensions"] < 1
                        or not has_evidence(space.get("evidence"))):
                    rejected.append("embedding-space-unverified")
                else:
                    requested_name = target.get("routeName")
                    if (not isinstance(requested_name, str)
                            or not re.fullmatch(r"embed-[a-z0-9-]{1,75}", requested_name)
                            or not requested_name.endswith(f"-{suffix}")):
                        rejected.append("embedding-route-name-invalid")
                    else:
                        route_name = requested_name
                        embedding_fingerprint = (space["identity"].strip(), space["dimensions"])
            entry["routes"].append({"name": route_name, "excluded": rejected})
            if rejected:
                continue
            previous_endpoint = group_endpoints.setdefault(route_name, endpoint)
            if previous_endpoint != endpoint:
                raise ValueError(f"Route name belongs to incompatible endpoints: {route_name}")
            if embedding_fingerprint is not None:
                previous_space = embedding_spaces.setdefault(route_name, embedding_fingerprint)
                if previous_space != embedding_fingerprint:
                    raise ValueError(f"Embedding-space mismatch for {route_name}")
            groups[route_name].append((row, target, endpoint))

    combos = []
    for name, candidates in sorted(groups.items()):
        candidates.sort(key=lambda item: (
            number(item[1].get("priority"), 1000),
            catalog_rank[(item[1]["catalogProvider"], item[1]["catalogId"])],
            item[1]["providerId"], item[1]["model"],
        ))
        models = [{"kind": "model", "providerId": target["providerId"], "model": target["model"]}
                  for _, target, _ in candidates]
        attempt_budget = min(len(models), requested_attempts)
        description = "Managed from llm_fallbacks. Priority order uses operator preference and canonical catalog rank."
        if name.endswith("free-demo"):
            description += " Public prompts only. Provider may retain or train on prompts."
        payload = {"name": name, "description": description, "strategy": "priority", "models": models,
                   "config": {"disableSessionStickiness": False, "maxGlobalAttempts": attempt_budget,
                              "comboTimeoutMs": deadline_ms, "maxRetries": 0, "maxSetRetries": 0}}
        if name in embedding_spaces:
            payload["dimensions"] = str(embedding_spaces[name][1])
        combos.append({"endpoint": candidates[0][2], "payload": payload,
                       "sharedQuotaGroups": sorted({text(t.get("quotaGroup"), "quotaGroup") for _, t, _ in candidates}),
                       "eligibleTargets": len(models), "attemptBudget": attempt_budget,
                       "comboTimeoutMs": deadline_ms,
                       "beyondAttemptBudget": models[attempt_budget:],
                       "executionLimits": "Stops at the first success, attempt budget, or whole-combo deadline. All eligible targets remain listed."})
    return {"version": 1, "asOf": as_of.isoformat(), "source": {
        "repository": "https://github.com/ai-llm-experiments/llm_fallbacks",
        "catalogSha256": catalog_hash, "policySha256": policy_hash,
        "catalogRows": len(catalog), "ranking": "priority, canonical catalog order, provider, model",
    }, "proposedCombos": combos, "targetDecisions": decisions,
        "unattestedCatalogRows": len(set(index) - {(t["catalogProvider"], t["catalogId"]) for t in decisions})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Explicit ISO timestamp makes output reproducible")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog, catalog_hash = read_json(args.catalog)
    policy, policy_hash = read_json(args.access)
    proposal = generate(catalog, policy, moment(args.as_of), catalog_hash, policy_hash)
    encoded = json.dumps(proposal, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(encoded)
    temporary.replace(args.output)
    print(f"Catalog rows {len(catalog)}; proposed combos {len(proposal['proposedCombos'])}")


if __name__ == "__main__":
    main()
