// Zero-config chat uses the cloud proxy from configs/chat_proxy.json.
window.LLM_FALLBACKS_CONFIG = {
  endpoints: ["https://llm-fallbacks-proxy.bodecloud.workers.dev"],
  guestToken: "llm-fallbacks-public",
  defaultModel: "",
  catalogUrl:
    "https://raw.githubusercontent.com/ai-llm-experiments/llm-provider-toolkit/main/configs/free_models.json",
  providerUrlsUrl:
    "https://raw.githubusercontent.com/ai-llm-experiments/llm-provider-toolkit/main/configs/provider_urls.json",
  chatProxyUrl:
    "https://raw.githubusercontent.com/ai-llm-experiments/llm-provider-toolkit/main/configs/chat_proxy.json",
  maxTokens: 512,
};
