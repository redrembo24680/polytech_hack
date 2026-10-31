// Server-safe core (no React/SWR). Server components import from "@/lib/api-core".
export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

/** Browser uses NEXT_PUBLIC_API_URL; server components (inside Docker) use INTERNAL_API_URL. */
export function baseUrl(): string {
  const pub = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
  if (typeof window === "undefined") return process.env.INTERNAL_API_URL ?? pub;
  return pub;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(baseUrl() + path, {
      ...init,
      method,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("network", "Не вдалося зʼєднатися з сервером", 0);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = undefined;
  }
  if (!res.ok) {
    const d = (data ?? {}) as { error?: string; message?: string };
    throw new ApiError(d.error ?? "http_error", d.message ?? res.statusText, res.status);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => request<T>("GET", path, undefined, init),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  del: <T = void>(path: string) => request<T>("DELETE", path),
};
