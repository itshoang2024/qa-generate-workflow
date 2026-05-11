const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000/api/v1";

export type Envelope<T> = { data: T; meta: Record<string, unknown> | null; error: null }
                       | { data: null; meta: null; error: { code: string; message: string; details?: string } };

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  const body = (await res.json()) as Envelope<T>;
  if (body.error) throw new Error(`${body.error.code}: ${body.error.message}`);
  if (body.data === null || body.data === undefined) throw new Error("Empty response.");
  return body.data;
}