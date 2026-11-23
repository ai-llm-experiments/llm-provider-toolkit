import type { CatalogEntry } from "./providers/browser-router";

/** Fired when the active chat model changes (picker, explorer, etc.). */
export const MODEL_CHANGED_EVENT = "llm-fallbacks:model-changed";

const PINNED_MODELS: { id: string; label: string }[] = [
  { id: "@cf/meta/llama-3.1-8b-instruct-fast", label: "Llama 3.1 8B Instruct (Cloudflare)" },
  { id: "free", label: "free (ranked alias)" },
  { id: "openrouter/free", label: "openrouter/free (OpenRouter router)" },
];

let sessionModel: string | null = null;
let catalogRef: CatalogEntry[] = [];

export function initModelSelection(catalog: CatalogEntry[]): void {
  catalogRef = catalog;
}

export function setCatalogRef(catalog: CatalogEntry[]): void {
  catalogRef = catalog;
}

/** Explicit model selection for this session. */
export function getActiveModel(fallbackDefault = ""): string {
  return sessionModel ?? fallbackDefault;
}

export function setActiveModel(id: string): void {
  const trimmed = id.trim();
  if (!trimmed) return;
  sessionModel = trimmed;
  window.dispatchEvent(
    new CustomEvent(MODEL_CHANGED_EVENT, { detail: { modelId: trimmed } })
  );
}

export function getPinnedModels(): readonly { id: string; label: string }[] {
  return PINNED_MODELS;
}

/** Top catalog entries by quality_score for the composer picker (max 50). */
export function getCatalogModels(limit = 50): CatalogEntry[] {
  const sorted = [...catalogRef].sort(
    (a, b) => (b.quality_score ?? 0) - (a.quality_score ?? 0)
  );
  return sorted.slice(0, limit);
}

export function modelOptionLabel(entry: CatalogEntry): string {
  const score =
    entry.quality_score !== undefined ? ` · ${entry.quality_score.toFixed(1)}` : "";
  return `${entry.id}${score}`;
}

export function findCatalogEntry(id: string): CatalogEntry | undefined {
  return catalogRef.find((entry) => entry.id === id);
}


/** Populate a picker without parsing catalog or user-provided strings as markup. */
export function fillModelPicker(select: HTMLSelectElement, selected: string, limit = 50): void {
  const placeholder = new Option("Choose a model", "");
  placeholder.disabled = true;
  const options = new Map(getPinnedModels().map(({ id, label }) => [id, label]));
  for (const entry of getCatalogModels(limit)) {
    if (!options.has(entry.id)) options.set(entry.id, modelOptionLabel(entry));
  }
  if (selected && !options.has(selected)) {
    const entry = findCatalogEntry(selected);
    options.set(selected, entry ? modelOptionLabel(entry) : selected);
  }
  select.replaceChildren(placeholder, ...Array.from(options, ([id, label]) => new Option(label, id)));
  select.value = selected;
}
