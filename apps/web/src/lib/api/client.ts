// Typed API client generated from FastAPI's OpenAPI schema (npm run gen:api). Do not hand-edit schema.d.ts.
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type RunRow = Schemas["RunRow"];
export type RunDetail = Schemas["RunDetail"];
export type Me = Schemas["Me"];
export type ApprovalIn = Schemas["ApprovalIn"];

export const api = createClient<paths>({ baseUrl: "/api", credentials: "include" });

// Live events use the same origin as the page (/api is proxied to FastAPI): no CORS, no cookie or
// host mismatch (localhost may resolve to IPv6 while the API listens on IPv4). Override with
// NEXT_PUBLIC_EVENTS_URL if a proxy in front buffers streams.
export const EVENTS_URL = process.env.NEXT_PUBLIC_EVENTS_URL ?? "/api/runs/stream";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Throw ApiError on any non-2xx, with the API's `detail` message when present. */
export async function unwrap<T>(p: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await p;
  if (!response.ok) {
    const detail =
      (error as { detail?: unknown } | undefined)?.detail ?? response.statusText ?? "Request failed";
    throw new ApiError(response.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}
