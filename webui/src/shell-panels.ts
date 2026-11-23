type PanelInit = (root: HTMLElement) => void;

const panels = new Map<string, PanelInit>();
const panelButtons = {
  sysSetting: "failover",
  byokSetting: "byok",
  tiersSetting: "tiers",
  explorerSetting: "explorer",
};
let activeTrigger: HTMLElement | null = null;

function showPanel(active?: HTMLElement): void {
  document.querySelectorAll<HTMLElement>(".shell-panel").forEach((panel) => {
    const open = panel === active;
    panel.classList.toggle("open", open);
    panel.inert = !open;
  });
  const mask = document.getElementById("sysMask");
  if (mask) mask.hidden = !active;
  const close = document.getElementById("closeSet");
  if (close) close.style.display = active ? "block" : "none";
}

export function registerShellPanel(id: string, init: PanelInit): void {
  panels.set(id, init);
  const el = document.getElementById(`panel-${id}`);
  if (el) init(el);
}

export function initShellPanels(): void {
  window.registerShellPanel = registerShellPanel;
  for (const [id, init] of panels) {
    const el = document.getElementById(`panel-${id}`);
    if (el) init(el);
  }
}

export function openShellPanel(id: string, trigger?: HTMLElement): void {
  const panel = document.getElementById(`shell-panel-${id}`);
  if (!panel) return;
  activeTrigger?.setAttribute("aria-expanded", "false");
  activeTrigger = trigger ?? null;
  activeTrigger?.setAttribute("aria-expanded", "true");
  showPanel(panel);
  panel.focus();
}

export function closeShellPanel(): void {
  showPanel();
  activeTrigger?.setAttribute("aria-expanded", "false");
  activeTrigger?.focus();
  activeTrigger = null;
}

export function bindTopBarButtons(): void {
  for (const [buttonId, panelId] of Object.entries(panelButtons)) {
    const button = document.getElementById(buttonId);
    button?.setAttribute("aria-controls", `shell-panel-${panelId}`);
    button?.setAttribute("aria-expanded", "false");
    button?.addEventListener("click", () => openShellPanel(panelId, button));
  }
  document.getElementById("closeSet")?.addEventListener("click", closeShellPanel);
  document.getElementById("sysMask")?.addEventListener("click", (event) => {
    if (event.target === event.currentTarget) closeShellPanel();
  });
  document.addEventListener("keydown", (event) => {
    if (!event.defaultPrevented && activeTrigger && event.key === "Escape") {
      event.preventDefault();
      closeShellPanel();
    }
  });
}
