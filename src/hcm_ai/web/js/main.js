import { ApiError, demoLogin, onUnauthorized } from "./api.js";
import { clearSession, getSession, sessionFromToken, setSession } from "./auth.js";
import { createChat } from "./chat.js";
import { mountDashboard } from "./dashboard.js";
import { h, setChildren } from "./dom.js";
import { mountEmployee } from "./employee.js";
import { notice } from "./ui.js";

const app = document.getElementById("app");

const ROLE_BLURB = {
  Admin: "Company-wide dashboard and AI summary",
  HR: "People dashboard, insights and AI summary",
  Employee: "My leave, attendance and smart leave form",
};

function showSignIn(message = null) {
  const status = h("div", { "aria-live": "polite" }, message ? notice("warn", message) : null);
  const tokenBox = h("textarea", { id: "jwt", rows: "3", "aria-label": "JWT from your login", placeholder: "Paste a JWT issued by your login service" });

  async function signInAs(role, button) {
    button.disabled = true;
    setChildren(status);
    try {
      setSession(await demoLogin(role));
      start();
    } catch (err) {
      const off = err instanceof ApiError && err.status === 404;
      setChildren(
        status,
        notice("error", off ? "Demo sign-in is switched off on this server. Paste a JWT below instead." : "Couldn't sign in. Please try again."),
      );
      if (off) tokenBox.closest("details").open = true;
      button.disabled = false;
    }
  }

  function useToken() {
    const session = sessionFromToken(tokenBox.value);
    if (!session) {
      setChildren(status, notice("error", "That token isn't valid or has expired."));
      return;
    }
    setSession(session);
    start();
  }

  setChildren(
    app,
    h(
      "main",
      { class: "signin" },
      h("h1", { text: "HCM Lite" }),
      h("p", { class: "lead", text: "AI assistant for HR, built into your dashboard." }),
      notice("info", "Demo build: sample company data. Login, employees, attendance, leave and payroll modules are not connected."),
      status,
      h(
        "div",
        { class: "role-cards", role: "group", "aria-label": "Sign in as" },
        ["Admin", "HR", "Employee"].map((role) => {
          const btn = h("button", { class: "role-card", type: "button" }, h("strong", { text: role }), h("span", { text: ROLE_BLURB[role] }));
          btn.addEventListener("click", () => signInAs(role, btn));
          return btn;
        }),
      ),
      h("details", {}, h("summary", { text: "Have a token? Sign in with a JWT" }), tokenBox, h("button", { class: "btn", type: "button", onClick: useToken }, "Use token")),
    ),
  );
}

function showApp(session) {
  const { user } = session;
  const chat = createChat(user.role);
  const main = h("main", { class: "content", id: "main" });
  const fab = h("button", { class: "fab", type: "button", "aria-controls": "chat", "aria-expanded": "false" }, "Ask AI");

  const setChat = (open) => {
    chat.element.classList.toggle("open", open);
    fab.setAttribute("aria-expanded", String(open));
    if (open) chat.input.focus();
    else fab.focus();
  };
  fab.addEventListener("click", () => setChat(true));
  chat.closeBtn.addEventListener("click", () => setChat(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && chat.element.classList.contains("open")) setChat(false);
  });

  const signOut = h("button", { class: "btn link", type: "button" }, "Sign out");
  signOut.addEventListener("click", () => {
    clearSession();
    showSignIn();
  });

  setChildren(
    app,
    h("a", { class: "skip", href: "#main", text: "Skip to content" }),
    h(
      "header",
      { class: "topbar" },
      h("strong", { class: "brand", text: "HCM Lite" }),
      h("span", { class: "chip role", text: user.role }),
      h("span", { class: "who", text: user.name }),
      h("span", { class: "spacer" }),
      signOut,
    ),
    h("div", { class: "layout" }, main, chat.element),
    fab,
  );

  if (user.role === "Employee") mountEmployee(main);
  else mountDashboard(main);
}

function start() {
  const session = getSession();
  if (session?.token && session.user) showApp(session);
  else showSignIn();
}

onUnauthorized(() => {
  clearSession();
  showSignIn("Your session ended. Please sign in again.");
});

start();
