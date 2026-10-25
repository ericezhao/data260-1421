import axios from "axios";

const TOKEN_KEY = "hw7_access_token";

export const api = axios.create({
  baseURL: import.meta.env.DEV ? "http://localhost:8521" : "",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function onSessionExpired(callback) {
  const id = api.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err.response?.status === 401 && !err.config.url.startsWith("/auth/")) {
        localStorage.removeItem(TOKEN_KEY);
        callback();
      }
      return Promise.reject(err);
    }
  );
  return () => api.interceptors.response.eject(id);
}

export function errorMessage(err) {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join("; ");
  }
  return detail || err.message;
}

export async function fetchInspectionById(id) {
  const res = await api.get(`/api/inspections/${id}`);
  return res.data;
}

export async function fetchOwners() {
  const res = await api.get("/api/owners", { params: { limit: 100 } });
  return res.data;
}

export async function login(username, password) {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  const res = await api.post("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  localStorage.setItem(TOKEN_KEY, res.data.access_token);
  return res.data;
}

export async function logout() {
  localStorage.removeItem(TOKEN_KEY);
  return { message: "logged out" };
}

export async function me() {
  const res = await api.get("/auth/me");
  return res.data;
}
