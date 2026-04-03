import axios from "axios";

/**
 * Surfaces FastAPI/Axios errors in the UI (detail string, validation array, or network).
 */
export function getAuthErrorMessage(
  err: unknown,
  fallback: string,
): string {
  if (!axios.isAxiosError(err)) {
    return fallback;
  }

  if (err.code === "ERR_NETWORK" || err.message === "Network Error") {
    const base =
      typeof process.env.NEXT_PUBLIC_API_URL === "string" &&
      process.env.NEXT_PUBLIC_API_URL.length > 0
        ? process.env.NEXT_PUBLIC_API_URL
        : "(NEXT_PUBLIC_API_URL not set)";
    return `Cannot reach the API at ${base}. Start the FastAPI backend and check .env.local.`;
  }

  const status = err.response?.status;
  const data = err.response?.data as
    | { detail?: unknown; error?: { message?: string } }
    | undefined;

  if (data?.error?.message) return data.error.message;

  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const parts = d.map((item: { msg?: string }) => item?.msg).filter(Boolean);
    if (parts.length) return parts.join(" ");
  }

  if (status === 401) return "Invalid email or password.";
  if (status === 400 && typeof d === "string") return d;
  if (status === 422) return "Invalid input. Check email and password format.";
  if (status && status >= 500) return "Server error. Check backend logs and database.";

  return fallback;
}
