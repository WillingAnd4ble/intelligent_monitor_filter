import axios from "axios";

const baseURL =
  (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "") || undefined;

export const apiClient = axios.create({
  baseURL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (typeof window !== "undefined" && status === 401) {
      window.dispatchEvent(new CustomEvent("auth:logout"));
      const path = window.location.pathname;
      if (
        !path.startsWith("/login") &&
        !path.startsWith("/register") &&
        path !== "/"
      ) {
        const next = encodeURIComponent(path + window.location.search);
        window.location.assign(`/login?next=${next}`);
      }
    }
    return Promise.reject(error);
  },
);
