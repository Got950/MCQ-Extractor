// Local dev: Vite proxies /api → localhost:8000. Production (Netlify): set VITE_API_URL.
const API_BASE = import.meta.env.VITE_API_URL || "/api";
const TOKEN_KEY = "mcq_token";
export const AUTH_EXPIRED_EVENT = "mcq:auth-expired";

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token, { remember } = {}) {
  try {
    if (remember) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.removeItem(TOKEN_KEY);
    } else {
      sessionStorage.setItem(TOKEN_KEY, token);
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* storage may be disabled */
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

const REQUEST_TIMEOUT_MS = 30_000;

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(
        "Server did not respond in time. Check that the backend is running on port 8000.",
      );
    }
      throw new Error(
        "Cannot reach the API server. Check that the backend is running and VITE_API_URL is set on Netlify.",
      );
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) {
    const isPublicAuth =
      path === "/auth/login" || path === "/auth/register";
    if (!isPublicAuth && token) {
      clearToken();
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    }
    const err = new Error(
      isPublicAuth ? "Invalid email or password" : "Not authenticated",
    );
    err.status = 401;
    throw err;
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      /* swallow */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

function jsonRequest(path, method, body) {
  return request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- Auth -----------------------------------------------------------------
export function register(email, password) {
  return jsonRequest("/auth/register", "POST", { email, password });
}

export function login(email, password) {
  return jsonRequest("/auth/login", "POST", { email, password });
}

export function me() {
  return request("/auth/me");
}

// --- Public ---------------------------------------------------------------
export function getProviders() {
  return request("/llm-providers");
}

export function getHealth() {
  return request("/health");
}

// --- Jobs (require auth) --------------------------------------------------
export function uploadPdf({ file, subject, language, provider }) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("subject", subject);
  fd.append("language", language);
  fd.append("provider", provider);
  return request("/upload", { method: "POST", body: fd, timeoutMs: 120_000 });
}

export function listJobs() {
  return request("/jobs");
}

export function getJob(jobId) {
  return request(`/jobs/${encodeURIComponent(jobId)}`);
}

export function retryJob(jobId) {
  return request(`/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
}

export function getQuestions(jobId) {
  return request(`/jobs/${encodeURIComponent(jobId)}/questions`);
}

export function updateQuestion(questionId, payload) {
  return jsonRequest(`/questions/${encodeURIComponent(questionId)}`, "PUT", payload);
}
