import type { Message } from "murm-ui";

export interface ExportSessionMeta {
  id: string;
  title?: string;
}

function messageText(message: Message): string {
  return message.blocks
    .filter((b) => b.type === "text")
    .map((b) => (b.type === "text" ? b.text : ""))
    .join("")
    .trim();
}

export function toMarkdown(messages: readonly Message[], meta?: ExportSessionMeta): string {
  const title = meta?.title?.trim() || "Chat export";
  const lines = [`# ${title.replace(/[\r\n]+/g, " ")}`, "", "_Exported from LLM Provider Toolkit_", ""];
  for (const message of messages) {
    const text = messageText(message);
    if (!text) continue;
    const heading = message.role === "user" ? "## User" : "## Assistant";
    const escaped = text.replace(/^(\\*##[ \t]+(?:User|Assistant)[ \t]*)$/gim, "\\$1");
    lines.push(heading, "", escaped, "");
  }
  return lines.join("\n").trimEnd() + "\n";
}

export function toJson(messages: readonly Message[], meta: ExportSessionMeta): string {
  return JSON.stringify(
    {
      id: meta.id,
      title: meta.title ?? null,
      exportedAt: new Date().toISOString(),
      messages: messages.map((m) => ({
        id: m.id,
        role: m.role,
        text: messageText(m),
      })),
    },
    null,
    2
  );
}

export function slugifyTitle(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  return slug || "chat";
}

export function exportFilename(ext: "md" | "json", title?: string): string {
  const date = new Date().toISOString().slice(0, 10);
  const slug = slugifyTitle(title || "chat");
  return `llm-provider-toolkit-${slug}-${date}.${ext}`;
}

export function downloadBlob(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
