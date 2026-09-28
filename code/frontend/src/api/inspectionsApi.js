import axios from "axios";

const api = axios.create({
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

export async function fetchInspections() {
  const res = await api.get("/api/inspections");
  return res.data;
}

export async function fetchInspectionById(id) {
  const res = await api.get(`/api/inspections/${id}`);
  return res.data;
}

export async function createInspection(payload) {
  const res = await api.post("/api/inspections", payload);
  return res.data;
}

export async function updateInspection(id, payload) {
  const res = await api.put(`/api/inspections/${id}`, payload);
  return res.data;
}

export async function deleteInspection(id) {
  const res = await api.delete(`/api/inspections/${id}`);
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
