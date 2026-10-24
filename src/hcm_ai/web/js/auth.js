// Session handling. The token lives in sessionStorage (cleared when the tab closes), with an
// in-memory fallback if storage is blocked. The server re-checks every request: nothing here is
// a security boundary.

const KEY = "hcm.session";
const ROLES = new Set(["Admin", "HR", "Employee"]);
let memory = null;

export function getSession() {
  if (memory) return memory;
  try {
    const raw = sessionStorage.getItem(KEY);
    memory = raw ? JSON.parse(raw) : null;
  } catch {
    memory = null;
  }
  return memory;
}

export function setSession(session) {
  memory = session;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    /* storage blocked: keep in memory */
  }
}

export function clearSession() {
  memory = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export const getToken = () => getSession()?.token ?? null;

export function decodeJwt(token) {
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** Build a UI session from a pasted JWT (display only; the server verifies it). */
export function sessionFromToken(token) {
  const payload = decodeJwt(token.trim());
  if (!payload || !ROLES.has(payload.role)) return null;
  if (payload.exp && payload.exp * 1000 < Date.now()) return null;
  return {
    token: token.trim(),
    user: {
      user_id: Number(payload.sub),
      role: payload.role,
      employee_id: payload.employee_id ?? null,
      name: payload.name ?? `${payload.role} user`,
    },
  };
}
