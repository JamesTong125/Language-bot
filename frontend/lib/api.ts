import { readSse } from "@/lib/sse";
import type {
  CorrectionsEvent,
  Hint,
  LanguagesResponse,
  PracticeSession,
  ProfileResponse,
  ProfileUpdate,
  Scenario,
  Turn,
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

  scenarios: () => request<{ scenarios: Scenario[] }>("/scenarios"),
  startSession: (scenarioId: number) =>
    request<PracticeSession>("/sessions", { method: "POST", body: json({ scenario_id: scenarioId }) }),
  getSession: (id: number) => request<PracticeSession>(`/sessions/${id}`),
  hint: (id: number) => request<Hint>(`/sessions/${id}/hint`, { method: "POST" }),
};

export interface TurnHandlers {
  onLearnerTurn: (turn: Turn) => void;
  onToken: (text: string) => void;
  /** The partner reply was saved. The stream may stay open for corrections. */
  onDone: (turn: Turn) => void;
  /** The partner reply failed. The learner message (if new) is still saved. */
  onReplyError: (message: string) => void;
  onCorrections: (event: CorrectionsEvent) => void;
}

/** Longest a whole stream may take: reply (with retries and fallback) plus corrections. */
const STREAM_TIMEOUT_MS = 150_000;

/**
 * Send a learner message (or retry the last reply), stream the partner reply, then wait
 * for corrections. Resolves when the stream ends. Rejects with ApiError only when the
 * request fails before the reply finished (network, HTTP error, or a cut-off stream).
 */
export async function streamTurn(
  sessionId: number,
  body: { text: string } | { retry: true },
  handlers: TurnHandlers,
): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);
  let replyFinished = false;
  try {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/sessions/${sessionId}/turns`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: json(body),
        signal: controller.signal,
      });
    } catch {
      throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
    }
    if (!response.ok || !response.body) {
      const errorBody: unknown = await response.json().catch(() => null);
      throw new ApiError(response.status, errorMessage(response.status, errorBody));
    }

    for await (const { event, data } of readSse(response.body)) {
      if (event === "learner_turn") handlers.onLearnerTurn(data as Turn);
      else if (event === "token") handlers.onToken((data as { text: string }).text);
      else if (event === "done") {
        replyFinished = true;
        handlers.onDone(data as Turn);
      } else if (event === "error") {
        replyFinished = true;
        handlers.onReplyError((data as { message: string }).message);
      } else if (event === "corrections") {
        handlers.onCorrections(data as CorrectionsEvent);
      }
    }
    if (!replyFinished) throw new ApiError(0, "The reply was cut off. Please try again.");
  } catch (err) {
    // After the reply, a dropped stream only means corrections didn't arrive live.
    if (replyFinished) return;
    if (err instanceof ApiError) throw err;
    if (controller.signal.aborted) throw new ApiError(0, "The reply took too long. Please try again.");
    throw new ApiError(0, "The reply was cut off. Please try again.");
  } finally {
    clearTimeout(timer);
  }
}