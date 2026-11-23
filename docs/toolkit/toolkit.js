// Older chat builds could leave a session hash on the workbench URL.
if (location.hash.startsWith("#/chat/")) {
  const chat = new URL("./chat/", location.href);
  chat.hash = location.hash;
  location.replace(chat);
}

const configRoot = "https://raw.githubusercontent.com/ai-llm-experiments/llm-provider-toolkit/main/configs/";
const $ = (id) => document.getElementById(id);
const selected = new Set();
const pageSize = 20;
const number = new Intl.NumberFormat();
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 5 });
let models = [];
let endpoints = {};
const providerRoutes = new Map();
let modelCounts = new Map();
let page = 0;
const price = (value) => Number.isFinite(value) ? money.format(value * 1e6) : "—";

function cell(row, value) {
  const target = row.insertCell();
  target.append(value);
  return target;
}

function render() {
  const query = $("query").value.trim().toLowerCase();
  const provider = $("provider").value;
  const mode = $("mode").value;
  const capability = $("capability").value;
  const key = $("sort").value;
  const filtered = models.filter((model) =>
    (!query || (model.id + " " + model.provider).toLowerCase().includes(query)) &&
    (!provider || model.provider === provider) &&
    (!mode || model.mode === mode) &&
    (!capability || model[capability] === true));
  if (key !== "name") {
    filtered.sort((a, b) => {
      const score = (item) => Number.isFinite(item[key]) ? (key === "max_input_tokens" ? -item[key] : item[key]) : Infinity;
      return (score(a) - score(b)) || a.id.localeCompare(b.id);
    });
  }
  const pages = Math.ceil(filtered.length / pageSize);
  page = Math.min(page, Math.max(0, pages - 1));
  $("rows").replaceChildren();
  for (const model of filtered.slice(page * pageSize, (page + 1) * pageSize)) {
    const row = $("rows").insertRow();
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = selected.has(model.id);
    toggle.setAttribute("aria-label", "Select " + model.id);
    toggle.onchange = () => {
      if (toggle.checked) selected.add(model.id);
      else selected.delete(model.id);
      renderExport();
    };
    const spec = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = model.id;
    const raw = document.createElement("pre");
    raw.textContent = JSON.stringify(model.raw, null, 2);
    spec.append(summary, raw);
    for (const value of [toggle, spec, model.provider, model.mode, price(model.input_cost_per_token),
      price(model.output_cost_per_token), Number.isFinite(model.max_input_tokens) ? number.format(model.max_input_tokens) : "—"]) cell(row, value);
  }
  $("status").textContent = number.format(filtered.length) + " of " + number.format(models.length) + " models";
  $("page").textContent = pages ? (page + 1) + " / " + pages : "0 pages";
  $("prev").disabled = page === 0;
  $("next").disabled = page + 1 >= pages;
}

function renderExport() {
  const selection = models.filter(({id}) => selected.has(id));
  $("comparison").replaceChildren();
  if (selection.length) {
    const table = document.createElement("table");
    const header = table.createTHead().insertRow();
    for (const label of ["Selected model", "Input / 1M", "Output / 1M", "Vision", "Tools"]) {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      header.append(th);
    }
    const body = table.createTBody();
    for (const model of selection) {
      const row = body.insertRow();
      for (const value of [model.id, price(model.input_cost_per_token), price(model.output_cost_per_token),
        model.supports_vision ? "Yes" : "—", model.supports_function_calling ? "Yes" : "—"]) cell(row, value);
    }
    $("comparison").append(table);
  }
  const modelList = selection.map(({id, provider}) => {
    const route = providerRoutes.get(provider);
    const unprefixed = id.startsWith(provider + "/") ? id.slice(provider.length + 1) : id;
    const routeId = [id, unprefixed].find((key) => route && Object.hasOwn(route.model_specs, key));
    const litellm_params = { model: id.startsWith(provider + "/") ? id : provider + "/" + id };
    if (routeId) {
      const key = routeId.includes("/") ? routeId : provider + "/" + routeId;
      litellm_params.model = key.startsWith("openai/") ? key : "openai/" + key;
      litellm_params.api_base = route.base_url;
      if (route.api_env_key_name) litellm_params.api_key = "os.environ/" + route.api_env_key_name;
      if (route.api_version) litellm_params.api_version = route.api_version;
    }
    return { model_name: id, litellm_params };
  });
  $("export").textContent = modelList.length ? JSON.stringify({model_list: modelList}, null, 2) : "No models selected.";
  $("download").disabled = $("clear").disabled = !modelList.length;
  $("download").textContent = modelList.length ? "Download " + modelList.length + " selected" : "Download selection";
}

$("filters").oninput = () => { page = 0; render(); };
$("filters").onsubmit = (event) => event.preventDefault();
$("prev").onclick = () => { page--; render(); };
$("next").onclick = () => { page++; render(); };
$("clear").onclick = () => { selected.clear(); render(); renderExport(); };
$("download").onclick = () => {
  const url = URL.createObjectURL(new Blob([$("export").textContent], { type: "application/yaml" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "litellm-selection.yaml";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$("sample").onclick = () => {
  $("payload").value = JSON.stringify({data: [{id: "example/chat-model", context_length: 32768, pricing: {prompt: "0.000001", completion: "0.000003"}}]}, null, 2);
};
$("parse").onclick = () => {
  try {
    const payload = JSON.parse($("payload").value);
    const entries = Array.isArray(payload) ? payload : payload?.data;
    if (!Array.isArray(entries) || entries.some((entry) => typeof entry?.id !== "string" || !entry.id.trim())) {
      throw new Error("Expected an array of models with string IDs, or an object with a data array.");
    }
    const numeric = (value) => (typeof value === "number" || (typeof value === "string" && value.trim())) && Number.isFinite(Number(value)) ? Number(value) : null;
    $("parsed").textContent = JSON.stringify(entries.map((entry) => ({
      id: entry.id, owned_by: entry.owned_by ?? null,
      context_length: numeric(entry.context_length),
      max_output_tokens: numeric(entry.top_provider?.max_completion_tokens),
      input_cost_per_token: numeric(entry.pricing?.prompt),
      output_cost_per_token: numeric(entry.pricing?.completion),
      input_modalities: entry.architecture?.input_modalities ?? null,
      output_modalities: entry.architecture?.output_modalities ?? null,
      supported_parameters: entry.supported_parameters ?? null,
    })), null, 2);
  } catch (error) {
    $("parsed").textContent = error.message;
  }
};

for (const [file, label] of Object.entries({
  "all_models.json": "Model catalog", "custom_providers.json": "Provider configurations",
  "provider_urls.json": "Provider base URLs", "litellm_config.yaml": "Full LiteLLM config",
})) {
  const link = document.createElement("a");
  link.href = configRoot + file;
  link.textContent = label;
  $("artifacts").append(document.createElement("li"));
  $("artifacts").lastElementChild.append(link);
}

async function readJson(file) {
  const response = await fetch(configRoot + file);
  if (!response.ok) throw new Error(file + " returned HTTP " + response.status);
  return response.json();
}

try {
  const [catalog, urls, providers] = await Promise.all(
    ["all_models.json", "provider_urls.json", "custom_providers.json"].map(readJson));
  endpoints = urls;
  for (const item of providers) if (item.base_url && item.model_specs) providerRoutes.set(item.provider_name, item);
  models = Object.entries(catalog).map(([id, raw]) => ({
    ...raw, id, raw, provider: raw.litellm_provider || id.split("/")[0], mode: raw.mode || "unknown",
  })).sort((a, b) => a.id.localeCompare(b.id));
  modelCounts = models.reduce((counts, {provider}) => counts.set(provider, (counts.get(provider) ?? 0) + 1), new Map());
  for (const field of ["provider", "mode"]) {
    for (const value of [...new Set(models.map((model) => model[field]))].sort()) $(field).add(new Option(value, value));
  }
  for (const [provider, endpoint] of Object.entries(endpoints).sort(([a], [b]) => a.localeCompare(b))) {
    const row = $("endpoints").insertRow();
    const link = document.createElement("a");
    link.href = "#models";
    link.textContent = provider;
    link.onclick = () => {
      $("query").value = $("mode").value = $("capability").value = "";
      $("provider").value = provider;
      page = 0;
      render();
    };
    if (![...$("provider").options].some((option) => option.value === provider)) link.removeAttribute("href");
    cell(row, link);
    cell(row, endpoint);
    cell(row, number.format(modelCounts.get(provider) ?? 0));
  }
  render();
} catch (error) {
  $("status").textContent = "Catalog unavailable. " + error.message + ". Reload to try again.";
}
