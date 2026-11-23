import { STORAGE_KEYS, loadJson, saveJson } from "./storage-keys";

export interface AppConfig {
  endpoints: string[];
  guestToken: string;
  defaultModel: string;
  catalogUrl: string;
  providerUrlsUrl: string;
  chatProxyUrl?: string;
  maxTokens: number;
}

export function normalizeEndpoints(list: unknown): string[] {
  if (!Array.isArray(list)) return [];
  return list
    .map((u) => String(u).trim().replace(/\/$/, ""))
    .filter((u) => u.length > 0);
}

export function readRuntimeConfig(): AppConfig {
  const cfg = window.LLM_FALLBACKS_CONFIG || ({} as AppConfig);
  const storedEndpoints = loadJson<string[]>(STORAGE_KEYS.endpoints, []);
  const endpoints =
    storedEndpoints.length > 0
      ? normalizeEndpoints(storedEndpoints)
      : normalizeEndpoints(cfg.endpoints || []);

  const savedDefault = localStorage.getItem(STORAGE_KEYS.defaultModel) || cfg.defaultModel || "";

  return {
    endpoints,
    guestToken:
      localStorage.getItem(STORAGE_KEYS.guestToken) ||
      cfg.guestToken ||
      "llm-fallbacks-public",
    defaultModel: ["free", "openrouter/free"].includes(savedDefault) ? "" : savedDefault,
    catalogUrl: cfg.catalogUrl || "",
    providerUrlsUrl: cfg.providerUrlsUrl || "",
    chatProxyUrl: cfg.chatProxyUrl,
    maxTokens: cfg.maxTokens || 512,
  };
}

export async function loadRuntimeConfig(): Promise<AppConfig> {
  return mergeChatProxyArtifact(readRuntimeConfig());
}

export function seedZeroConfigFromPageConfig(): void {
  const cfg = window.LLM_FALLBACKS_CONFIG;
  if (!cfg) return;

  if (!localStorage.getItem(STORAGE_KEYS.guestToken) && cfg.guestToken) {
    localStorage.setItem(STORAGE_KEYS.guestToken, cfg.guestToken);
  }
}

export async function mergeChatProxyArtifact(config: AppConfig): Promise<AppConfig> {
  if (!config.chatProxyUrl) return config;
  try {
    const res = await fetch(config.chatProxyUrl, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return config;
    const proxyCfg = (await res.json()) as {
      endpoints?: string[];
      guestToken?: string;
    };
    const published = normalizeEndpoints(proxyCfg.endpoints);
    const hasSavedEndpoints = normalizeEndpoints(loadJson<string[]>(STORAGE_KEYS.endpoints, [])).length > 0;
    const endpoints = hasSavedEndpoints ? config.endpoints : [...config.endpoints, ...published];
    return {
      ...config,
      endpoints: [...new Set(endpoints)],
      guestToken: localStorage.getItem(STORAGE_KEYS.guestToken) || proxyCfg.guestToken || config.guestToken,
    };
  } catch {
    return config;
  }
}
