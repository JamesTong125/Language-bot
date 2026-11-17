import type {
  LanguagesResponse,
  ProfileResponse,
  ProfileUpdate,
  User,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

/** Turn a FastAPI error body into one readable sentence. */
function errorMessage(status: number, body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const issue = detail[0] as ValidationIssue;
      const field = issue.loc?.filter((part) => part !== "body").join(".");
      const msg = (issue.msg ?? "Invalid value").replace(/^Value error, /, "");
      return field ? `${field.replace(/_/g, " ")}: ${msg}` : msg;
    }
  }
  if (status >= 500) return "The server had a problem. Please try again.";
  return `Request failed (${status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, errorMessage(response.status, body));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (body: unknown): string => JSON.stringify(body);

export const api = {
  languages: () => request<LanguagesResponse>("/languages"),

  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: json({ email, password }) }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: json({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),

  getProfile: () => request<ProfileResponse>("/profile"),
  updateProfile: (update: ProfileUpdate) =>
    request<ProfileResponse>("/profile", { method: "PUT", body: json(update) }),

  exportAccount: async (): Promise<Blob> => {
    const data = await request<unknown>("/account/export");
    return new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  },
  deleteAccount: (password: string) =>
    request<void>("/account", { method: "DELETE", body: json({ password }) }),
};
