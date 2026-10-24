// Chat panel: POST /ai/chat. AI text is rendered through renderRich (DOM nodes, no innerHTML).

import { api, describeError, ApiError } from "./api.js";
import { h, setChildren } from "./dom.js";
import { renderRich } from "./render.js";
import { aiLabel, startCountdown } from "./ui.js";

const SUGGESTIONS = {
  staff: [
    "How many active employees are in Engineering?",
    "Who came late most often this month?",
    "What is this month's attendance rate?",
    "What time is the late cutoff?",
  ],
  Employee: [
    "How many sick leaves do I have left this year?",
    "What is Sara Malik's salary?",
    "How many casual leaves do I get per year?",
    "What is my attendance rate this month?",
  ],
};

export function createChat(role) {
  const messages = [];
  let pending = false;
  let cancelCountdown = null;

  const list = h("div", { class: "chat-log", role: "log", "aria-live": "polite", "aria-label": "Conversation" });
  const input = h("textarea", {
    id: "chat-input",
    rows: "2",
    maxlength: "1000",
    placeholder: "Ask about your data or company policy",
    "aria-label": "Your question",
    onKeydown: (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send(input.value);
      }
    },
  });
  const sendBtn = h("button", { class: "btn primary", type: "submit" }, "Send");
  const form = h("form", { class: "chat-form", onSubmit: (e) => { e.preventDefault(); send(input.value); } }, input, sendBtn);
  const chips = h(
    "div",
    { class: "chips", "aria-label": "Suggested questions" },
    (SUGGESTIONS[role] ?? SUGGESTIONS.staff).map((q) => h("button", { class: "chip", type: "button", onClick: () => send(q) }, q)),
  );
  const closeBtn = h("button", { class: "btn link chat-close", type: "button", "aria-label": "Close assistant" }, "Close");
  const clearBtn = h("button", { class: "btn link", type: "button", onClick: () => reset() }, "Clear");

  const element = h(
    "aside",
    { class: "chat", id: "chat", "aria-label": "AI assistant" },
    h("header", { class: "chat-head" }, h("h2", { text: "Ask the assistant" }), aiLabel(), h("span", { class: "spacer" }), clearBtn, closeBtn),
    list,
    chips,
    form,
    h("p", { class: "chat-foot muted", text: "Answers use only data you are allowed to see and company policy." }),
  );

  function reset() {
    cancelCountdown?.();
    messages.length = 0;
    pending = false;
    setBusy(false);
    render();
  }

  function setBusy(busy) {
    pending = busy;
    sendBtn.disabled = busy;
    input.disabled = busy;
  }

  function bubble(m) {
    if (m.role === "user") return h("div", { class: "msg user" }, h("p", { text: m.text }));
    if (m.kind === "thinking") {
      return h("div", { class: "msg ai", "aria-busy": "true" }, h("span", { class: "dots", "aria-label": "Thinking" }, h("i"), h("i"), h("i")));
    }
    const failed = m.kind === "error";
    return h(
      "div",
      { class: `msg ai${failed ? " failed" : ""}` },
      failed ? h("p", { text: m.text }) : renderRich(m.text),
      failed ? m.retry && h("button", { class: "btn link", type: "button", onClick: m.retry }, "Try again") : h("div", { class: "msg-meta" }, aiLabel()),
    );
  }

  function render() {
    chips.hidden = messages.length > 0;
    setChildren(list, messages.map(bubble));
    list.scrollTop = list.scrollHeight;
  }

  async function send(raw) {
    const text = raw.trim();
    if (!text || pending) return;
    input.value = "";
    messages.push({ role: "user", text });
    messages.push({ role: "ai", kind: "thinking" });
    setBusy(true);
    render();

    let reply;
    try {
      const res = await api("/ai/chat", { method: "POST", body: { message: text } });
      reply = res.success
        ? { role: "ai", kind: "answer", text: res.answer }
        : { role: "ai", kind: "error", text: res.answer, retry: () => retryLast(text) };
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        messages.pop(); // drop the "thinking" bubble; the countdown note replaces it
        limitCountdown(err.retryAfter ?? 60);
        return;
      }
      reply = { role: "ai", kind: "error", text: describeError(err), retry: () => retryLast(text) };
    }
    messages.pop();
    messages.push(reply);
    setBusy(false);
    render();
    input.focus();
  }

  function retryLast(text) {
    messages.splice(-2, 2); // drop the failed exchange, then ask again
    send(text);
  }

  function limitCountdown(seconds) {
    cancelCountdown?.();
    setBusy(true);
    const note = { role: "ai", kind: "error", text: "" };
    messages.push(note);
    cancelCountdown = startCountdown(
      seconds,
      (left) => {
        note.text = `Hourly AI limit reached. You can ask again in ${left} s.`;
        render();
      },
      () => {
        messages.splice(messages.indexOf(note), 1);
        setBusy(false);
        render();
      },
    );
  }

  render();
  return { element, closeBtn, input };
}
