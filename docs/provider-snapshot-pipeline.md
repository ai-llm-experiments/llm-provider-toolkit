# Offline multi-provider route pipeline

`scripts/import_provider_snapshots.py` consumes saved snapshots for any configured `provider_catalogs.PROVIDER_CATALOGS` parser in llm_fallbacks. The current registry includes Kilo, OpenRouter, Groq, Cerebras, Google AI Studio and Hugging Face. The parser and pricing implementation come from the selected repository, with helper hashes recorded in the report. It loads pure files directly and skips package/config discovery. Its CLI denies networking.

Run from the repository root with explicit paths and evaluation time.

```bash
python scripts/import_provider_snapshots.py \
  --repository . \
  --manifest /path/to/snapshots.json \
  --evidence /path/to/evidence.json \
  --as-of 2026-11-16T01:00:00Z \
  --output-dir /path/to/proposal-review
```

Snapshot paths are resolved from the process working directory. One complete snapshot per provider is allowed. Pagination and count completeness follow the repository parser. Each input is limited to 16 MiB, individual arrays to 20,000 rows, and the combined candidate catalog to the route adapter's 20,000-row bound. Relative and absolute snapshot paths are accepted.

The manifest has this shape. Replace the paths with existing saved provider responses and record their actual observation times.

```json
{
  "version": 1,
  "snapshots": [
    {"provider": "kilo", "path": "/path/to/kilo-models.json", "observedAt": "2026-11-16T00:00:00Z"},
    {"provider": "groq", "path": "/path/to/groq-models.json", "observedAt": "2026-11-16T00:00:00Z"},
    {"provider": "google_ai_studio", "path": "/path/to/google-models.json", "observedAt": "2026-11-16T00:00:00Z"}
  ]
}
```

A minimal evidence input is `{"version":1}`. It creates candidate metadata from explicitly eligible catalog rows while leaving route admission blocked. Credentials have no supported input field. Strict object-field allowlists reject accidental `apiKey`, `token` and other unexpected fields. Evidence reference strings should point to receipts and must never contain credentials.

For an admitted text route, an operator-supplied evidence record has this shape. The example values describe a synthetic fixture and establish no live account, price or privacy facts.

```json
{
  "version": 1,
  "maxAgeHours": 24,
  "comboEndpoints": ["chat/completions"],
  "maxGlobalAttempts": 200,
  "comboTimeoutMs": 600000,
  "accounts": [{
    "provider": "groq",
    "connected": true,
    "providerScopeApproved": true,
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-account-scope"]
  }],
  "modelChecks": [{
    "provider": "groq",
    "model": "exact-upstream-model-id",
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-successful-request"],
    "mode": "chat",
    "modeEvidence": ["receipt-endpoint-contract"],
    "verifiedPricing": {
      "prices": {"prompt": "0", "completion": "0"},
      "verifiedAt": "2026-11-16T00:00:00Z",
      "evidence": ["receipt-complete-account-price-contract"]
    },
    "privacy": "private-approved",
    "purposes": ["text"],
    "endpoints": ["chat/completions"],
    "pricesComplete": true,
    "freeOnlyEnforced": true,
    "requestSucceeded": true,
    "quotaGroup": "groq-shared-account"
  }]
}
```

`verifiedPricing` can supply zero-price metadata only when a saved provider response has no reported pricing. It cannot override existing positive, invalid or partial provider pricing. The evidence must establish all applicable account charges and enforcement, including quota exhaustion behavior. The pipeline validates evidence structure and freshness. The operator remains responsible for the truth of the referenced receipts.

An unknown endpoint mode can be supplied through a fresh model check with nonblank `modeEvidence`. Known endpoint modes remain authoritative. Capability metadata remains the provider parser's responsibility. A local mode receipt does not assert tools or task suitability. Agent/coding routes still require catalog tools support and `toolsVerified`. Coding/persona routes additionally require the existing adapter's purpose evidence.

Every supplied timestamp is validated independently before aggregation. Future or stale account, model, pricing and snapshot observations reject the run. Missing checks keep privacy unknown and admission disabled. Privacy can be `private-approved` or `public-demo` only with verified model-check evidence. Demo targets retain the adapter's `free-demo` naming. Account approval covers every account that the runtime provider ID might select. Exact registry provider IDs are the default; alternate node IDs require independently verified [runtime mappings](runtime-provider-mapping.md).

The four outputs are `catalog.candidate.json`, `access.draft.json`, `proposal.json` and `import-report.json`. They contain exact upstream IDs, full source hashes, dispositions and unmatched checks. Candidate rank uses the repository's quality heuristic descending, then provider and exact model ID. Target priority and session stickiness follow the existing OmniRoute adapter. All eligible targets remain listed. Per-request attempts retain the adapter's explicit maximum of 200 and whole-combo deadline, with beyond-budget targets reported.

Media and other unsupported pricing contracts remain excluded by the repository's explicit-zero policy. Input-only embeddings can appear as catalog candidates, but the current route adapter requires both numeric token-price fields, so incomplete embedding route evidence remains excluded. This pipeline does not create either price dimension or an embedding-space identity. Preserve those compatibility boundaries when reviewing generated outputs.

## Inline verification receipt

An in-memory three-provider snapshot matrix covered Kilo, Groq and Google AI Studio. Kilo supplied complete catalog zero prices. Groq supplied unknown prices and mode, then required explicit fresh local receipts for both. Google remained excluded with unknown price metadata. Explicit account/model evidence produced a deterministic two-provider text proposal. Missing evidence, unknown privacy, mismatched exact IDs, future account/pricing times and credential-shaped fields stayed blocked or rejected. Python socket audit hooks denied network use throughout. The verification created no test files and made no provider requests.

## Review reconciliation

Malformed provider `pricing` values, including strings, lists and booleans, reject the entire input. Local price evidence is eligible only when provider pricing is absent or explicitly null. An empty or partial provider pricing object remains authoritative and cannot be replaced.

Nested purpose evidence accepts known route-purpose keys with nonblank string references. Embedding-space objects accept only identity, positive integer dimensions and string receipt references. Priority is finite numeric data, route names and quota groups are strings, endpoint/purpose arrays contain strings, and flags are booleans. These rules apply to every supplied check, including unused fields and checks that routing would exclude.

Catalog and access hashes in `proposal.json` use the exact UTF-8 bytes emitted to their respective files, including indentation and final newline. The same serialization function produces both artifacts and their hashes.

Additional inline adversarial checks reject malformed provider price metadata and nested credential-shaped objects in purpose evidence, embedding space, priority, route name, endpoint/purpose arrays and flags. Absent/null pricing with explicit fresh proof retains the valid baseline, while partial pricing remains excluded. Exact-byte catalog/access hash comparisons pass with networking denied.
