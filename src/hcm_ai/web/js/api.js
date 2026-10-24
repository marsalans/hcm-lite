// Same-origin API client. The browser only talks to this backend: never to an AI provider.

import { getToken } from "./auth.js";
import { parseRetryAfter } from "./format.js";

export class ApiError extends Error {
  constructor(status, detail, retryAfter = null) {
    super(detail);
    this.status = status; // 0 = network/timeout
    this.detail = detail;
    this.retryAfter = retryAfter;
  }
}

let unauthorizedHandler = () => {};
export const onUnauthorized = (fn) => {
  unauthorizedHandler = fn;
};

export async function api(path, { method = "GET", body, auth = true, timeoutMs = 25_000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const token = getToken();
    if (auth && token) headers.Authorization = `Bearer ${token}`;

    let res;
    try {
      res = await fetch(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      throw new ApiError(0, err?.name === "AbortError" ? "timeout" : "network");
    }

    let data = null;
    try {
      data = await res.json();
    } catch {
      /* empty or non-JSON body */
    }
    if (res.ok) return data;

    if (res.status === 401 && auth) unauthorizedHandler();
    const detail = typeof data?.detail === "string" ? data.detail : "error";
    const retry = res.status === 429 ? parseRetryAfter(res.headers.get("Retry-After")) : null;
    throw new ApiError(res.status, detail, retry);
  } finally {
    clearTimeout(timer);
  }
}

export const demoLogin = (role) => api("/auth/demo-login", { method: "POST", body: { role }, auth: false });

/** Plain-language message for an error, safe to show to users. */
export function describeError(err) {
  if (!(err instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (err.status) {
    case 0:
      return err.detail === "timeout"
        ? "The server took too long to answer. Please try again."
        : "Can't reach the server. Check your connection and try again.";
    case 403:
      return "Your role isn't allowed to do that.";
    case 413:
    case 422:
      return "That input isn't valid. Please shorten or change it.";
    case 429:
      return `You've reached the hourly AI limit. Try again in ${err.retryAfter ?? 60} seconds.`;
    default:
      return "Something went wrong on the server. Please try again.";
  }
}
