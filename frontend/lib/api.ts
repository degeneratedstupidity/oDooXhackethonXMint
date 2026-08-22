"use client";

const ACCESS_KEY = "dayflow.access";
const REFRESH_KEY = "dayflow.refresh";

export type ApiError = {
  status: number;
  /** Field name -> messages, as returned by DRF serializers. */
  fields: Record<string, string[]>;
  message: string;
};

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function storeTokens(tokens: { access: string; refresh: string }) {
  window.localStorage.setItem(ACCESS_KEY, tokens.access);
  window.localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearTokens() {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

/** Turns a DRF error body into a predictable shape the forms can render inline. */
function toApiError(status: number, body: unknown): ApiError {
  const fields: Record<string, string[]> = {};
  let message = "Something went wrong. Please try again.";

  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.detail === "string") {
      message = record.detail;
    }
    for (const [key, value] of Object.entries(record)) {
      if (key === "detail") continue;
      const list = Array.isArray(value) ? value.map(String) : [String(value)];
      fields[key] = list;
      if (key === "non_field_errors") message = list[0];
    }
    // A single field error reads better than the generic fallback.
    const keys = Object.keys(fields);
    if (keys.length && message === "Something went wrong. Please try again.") {
      message = fields[keys[0]][0];
    }
  }

  return { status, fields, message };
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAccessToken();
  const isFormData = options.body instanceof FormData;

  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw toApiError(response.status, body);
  }
  return body as T;
}
