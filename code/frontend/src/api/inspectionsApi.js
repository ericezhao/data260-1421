import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.DEV ? "http://localhost:8521" : "",
  withCredentials: true,
});

// run callback when a protected request gets 401 (session expired or invalid)
// /auth/* is skipped: /auth/me returns 401 when simply not logged in, /auth/login when password is wrong
export function onSessionExpired(callback) {
  const id = api.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err.response?.status === 401 && !err.config.url.startsWith("/auth/")) {
        callback();
      }
      return Promise.reject(err);
    }
  );
  return () => api.interceptors.response.eject(id);
}

// FastAPI sends detail as a string (404/409) or a list of field errors (422)
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

export async function login(email, password) {
  const res = await api.post("/auth/login", { email, password });
  return res.data;
}

export async function logout() {
  const res = await api.post("/auth/logout");
  return res.data;
}

export async function me() {
  const res = await api.get("/auth/me");
  return res.data;
}
