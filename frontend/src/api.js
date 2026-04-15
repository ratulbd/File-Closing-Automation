// API Base URL - configurable for different environments
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("token");
}

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const fetchOptions = {
    ...options,
    headers,
  };

  const res = await fetch(url, fetchOptions);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return data;
}

export const api = {
  login: (email, password) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request("/auth/me"),
  getDashboard: () => request("/dashboard"),
  getFiles: () => request("/files"),
  getFile: (id) => request(`/files/${id}`),
  createFile: (data) =>
    request("/files", { method: "POST", body: JSON.stringify(data) }),
  acknowledge: (id) =>
    request(`/files/${id}/acknowledge`, { method: "POST" }),
  forward: (id, data) =>
    request(`/files/${id}/forward`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  reject: (id, data) =>
    request(`/files/${id}/reject`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
