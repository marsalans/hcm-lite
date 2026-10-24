// Safe rich-text for AI output: only paragraphs, "- " bullets and **bold**, built as DOM nodes.
// The parsing functions are pure (unit-tested); nothing here ever touches innerHTML.

import { h } from "./dom.js";

const BULLET_RE = /^\s*(?:[-*•])\s+(.*)$/;
const BOLD_RE = /\*\*(.+?)\*\*/g;

export function parseInline(text) {
  const parts = [];
  let last = 0;
  for (const match of String(text).matchAll(BOLD_RE)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), bold: false });
    parts.push({ text: match[1], bold: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), bold: false });
  return parts;
}

export function parseBlocks(text) {
  const blocks = [];
  for (const raw of String(text ?? "").split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    const bullet = BULLET_RE.exec(line);
    if (bullet) {
      const last = blocks.at(-1);
      if (last?.type === "list") last.items.push(parseInline(bullet[1]));
      else blocks.push({ type: "list", items: [parseInline(bullet[1])] });
    } else {
      blocks.push({ type: "p", inline: parseInline(line.trim()) });
    }
  }
  return blocks;
}

const inlineNodes = (parts) =>
  parts.map((p) => (p.bold ? h("strong", { text: p.text }) : p.text));

export function renderRich(text) {
  const nodes = parseBlocks(text).map((block) =>
    block.type === "list"
      ? h("ul", {}, block.items.map((item) => h("li", {}, inlineNodes(item))))
      : h("p", {}, inlineNodes(block.inline)),
  );
  return h("div", { class: "rich" }, nodes);
}
