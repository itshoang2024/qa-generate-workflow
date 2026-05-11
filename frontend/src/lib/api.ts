/**
 * Envelope-aware fetch wrapper. Every backend response is
 * `{ data, meta, error }` (see `backend/app/domain/responses.py`); this
 * module unwraps to `data` on success and throws an `ApiError` on failure.
 */

const DEFAULT_BASE = "http://127.0.0.1:8000/api/v1";

export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE?.trim() || DEFAULT_BASE;

export interface EnvelopeMeta {
  request_id: string;
}

export interface EnvelopeError {
  code: string;
  message: string;
  details?: unknown;
}

export type Envelope<T> =
  | { data: T; meta: EnvelopeMeta; error: null }
  | { data: null; meta: EnvelopeMeta; error: EnvelopeError };

export class ApiError extends Error {
  readonly code: string;
  readonly httpStatus: number;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(
    code: string,
    message: string,
    httpStatus: number,
    options?: { details?: unknown; requestId?: string }
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.httpStatus = httpStatus;
    this.details = options?.details;
    this.requestId = options?.requestId;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

/**
 * Call a backend endpoint and unwrap the envelope.
 *
 * Throws `ApiError` when the backend returns an `error` envelope, when the
 * HTTP layer fails, or when the response is malformed.
 */
export async function api<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, signal, headers } = options;
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body:
        body === undefined
          ? undefined
          : typeof body === "string"
            ? body
            : JSON.stringify(body),
      cache: "no-store",
      signal,
    });
  } catch (cause) {
    throw new ApiError(
      "network_error",
      cause instanceof Error ? cause.message : "Network request failed.",
      0,
      { details: cause }
    );
  }

  let parsed: Envelope<T>;
  try {
    parsed = (await response.json()) as Envelope<T>;
  } catch (cause) {
    throw new ApiError(
      "invalid_envelope",
      `Response from ${path} was not valid JSON.`,
      response.status,
      { details: cause }
    );
  }

  if (parsed.error) {
    throw new ApiError(parsed.error.code, parsed.error.message, response.status, {
      details: parsed.error.details,
      requestId: parsed.meta?.request_id,
    });
  }

  if (parsed.data === null || parsed.data === undefined) {
    throw new ApiError(
      "empty_envelope",
      `Empty data envelope from ${path}.`,
      response.status,
      { requestId: parsed.meta?.request_id }
    );
  }

  return parsed.data;
}
