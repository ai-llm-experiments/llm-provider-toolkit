import type { ChatPlugin, Message } from "murm-ui";
import type { ChatEngine } from "murm-ui";
import { messageHasImage } from "../../providers/message-openai";

function extractText(msg: Message): string {
  return msg.blocks
    .filter((b) => b.type === "text")
    .map((b) => (b.type === "text" ? b.text : ""))
    .join("");
}

function findUserForAssistant(engine: ChatEngine, assistantMsg: Message): Message | null {
  const messages = engine.state.messages;
  const idx = messages.findIndex((m) => m.id === assistantMsg.id);
  if (idx <= 0) return null;
  for (let i = idx - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") return messages[i];
  }
  return null;
}

const ICON_REGEN = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>`;
const ICON_EDIT = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;

export function MessageActionsPlugin(): ChatPlugin {
  let engine: ChatEngine | null = null;
  let editDialog: HTMLDialogElement | null = null;
  let editText: HTMLTextAreaElement | null = null;
  let target: Message | null = null;

  return {
    name: "message-actions",
    onMount(ctx) {
      engine = ctx.engine;
      const dialog = document.createElement("dialog");
      dialog.className = "lf-chat-dialog";
      dialog.setAttribute("aria-labelledby", "lf-edit-heading");
      dialog.innerHTML = `
        <form method="dialog">
          <h2 id="lf-edit-heading">Edit message</h2>
          <label for="lf-edit-text">Message</label>
          <textarea id="lf-edit-text" rows="5" autofocus></textarea>
          <p>Resending replaces messages after this one.</p>
          <div class="lf-dialog-actions">
            <button value="cancel">Cancel</button>
            <button value="resend">Resend</button>
          </div>
        </form>
      `;
      document.body.append(dialog);
      editDialog = dialog;
      editText = dialog.querySelector("textarea");
      dialog.addEventListener("close", () => {
        const message = target;
        const text = editText?.value.trim() ?? "";
        target = null;
        if (!message || dialog.returnValue !== "resend" || !engine || engine.isBusy) return;
        if (!text && !messageHasImage(message)) return;
        if (text !== extractText(message).trim()) engine.editAndResubmit(message.id, text);
      });

    },
    getActionButtons(msg) {
      if (!engine) return [];

      if (msg.role === "assistant" && !msg.ephemeral && extractText(msg).trim()) {
        return [
          {
            id: "regenerate",
            title: "Regenerate response",
            iconHtml: ICON_REGEN,
            onClick: ({ message }) => {
              if (!engine || engine.isBusy) return;
              const userMsg = findUserForAssistant(engine, message);
              if (!userMsg) return;
              const text = extractText(userMsg);
              if (!text.trim() && !messageHasImage(userMsg)) return;
              engine.editAndResubmit(userMsg.id, text);
            },
          },
        ];
      }

      if (msg.role === "user" && extractText(msg).trim()) {
        return [
          {
            id: "edit",
            title: "Edit message",
            iconHtml: ICON_EDIT,
            onClick: ({ message }) => {
              if (!engine || engine.isBusy || !editDialog || !editText) return;
              target = message;
              editDialog.returnValue = "cancel";
              editText.value = extractText(message);
              editDialog.showModal();
            },
          },
        ];
      }

      return [];
    },
    destroy() {
      editDialog?.remove();
      target = null;
      engine = null;
    },
  };
}
