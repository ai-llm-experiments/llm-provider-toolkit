import type { ChatPlugin } from "murm-ui";
import { catalogSummaryLine } from "../../catalog-display";
import {
  findCatalogEntry,
  getActiveModel,
  fillModelPicker,
  getPinnedModels,
  MODEL_CHANGED_EVENT,
  setActiveModel,
} from "../../model-selection";

export function ModelPickerPlugin(): ChatPlugin {
  let selectEl: HTMLSelectElement | null = null;
  let detailEl: HTMLElement | null = null;

  function syncDetail(): void {
    if (!detailEl) return;
    const active = getActiveModel();
    const pinned = getPinnedModels().find((p) => p.id === active);
    if (pinned) {
      detailEl.textContent = pinned.id.includes("free") ? "Provider-managed routing option" : "";
      return;
    }
    const entry = findCatalogEntry(active);
    detailEl.textContent = entry ? catalogSummaryLine(entry) : active;
  }

  function populateOptions(): void {
    if (selectEl) fillModelPicker(selectEl, getActiveModel());
  }

  return {
    name: "model-picker",
    beforeSubmit: async (request) => {
      return {
        options: {
          ...request.options,
          model: getActiveModel(),
        },
      };
    },
    onMount(ctx) {
      const form = ctx.container.querySelector(".mur-chat-form-container");
      if (!form) return;

      const wrapper = document.createElement("div");
      wrapper.className = "lf-model-picker-row";
      wrapper.innerHTML = `
        <div class="lf-model-picker-main">
          <label class="lf-model-picker-label">
            <span class="lf-model-picker-title">Model</span>
            <select class="lf-model-picker-select" aria-label="Chat model"></select>
          </label>
          <p id="lf-model-detail" class="lf-model-detail" aria-live="polite"></p>
        </div>
        <div class="lf-model-picker-info">
          <a class="lf-model-rank-link" href="../#models">Browse the catalog</a>
        </div>
      `;

      form.insertBefore(wrapper, form.firstChild);
      selectEl = wrapper.querySelector(".lf-model-picker-select");
      detailEl = wrapper.querySelector("#lf-model-detail");
      if (!selectEl) return;

      populateOptions();
      syncDetail();
      selectEl.addEventListener("change", () => {
        setActiveModel(selectEl!.value);
        syncDetail();
      });

      window.addEventListener(MODEL_CHANGED_EVENT, populateOptions);
      window.addEventListener(MODEL_CHANGED_EVENT, syncDetail);
    },
    destroy() {
      window.removeEventListener(MODEL_CHANGED_EVENT, populateOptions);
      window.removeEventListener(MODEL_CHANGED_EVENT, syncDetail);
    },
  };
}

/** Re-export for explorer sync without importing plugin internals */
export { setActiveModel, MODEL_CHANGED_EVENT };
