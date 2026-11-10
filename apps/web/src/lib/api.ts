// Thin typed client for the Pramaan API.
// The session is an httpOnly cookie set by the API: JavaScript never sees the token, so an XSS bug can't steal it.
// Every request therefore sends credentials; there is nothing to store in localStorage.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function detail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  }
  return fallback;
}

export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { json, auth = true, headers, ...rest } = init;
  const h = new Headers(headers);
  if (json !== undefined) h.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      credentials: auth ? "include" : "omit", // auth:false = a public call; don't send the session cookie
      headers: h,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "Can't reach the Pramaan server. Is the API running?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detail(body, `Request failed (${res.status})`));
  return body as T;
}

/** Live agent stream. No token in the URL (URLs end up in logs): the browser sends the session cookie. */
export function streamUrl(profileId?: string): string {
  const q = new URLSearchParams();
  if (profileId) q.set("profile_id", profileId);
  return `${API_URL}/v1/agents/stream${q.size ? `?${q}` : ""}`;
}
