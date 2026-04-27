import { appEnv } from "@/lib/env";
import { getAuthSession } from "@/lib/auth-storage";
import type {
  ApiEnvelope,
  ApiErrorPayload,
  HttpMethod,
  QueryParams,
} from "@/types/api";

type SerializableBody = object;
type RequestBody =
  | string
  | FormData
  | URLSearchParams
  | Blob
  | ArrayBuffer
  | SerializableBody
  | null
  | undefined;
type NormalizedRequestBody =
  | string
  | FormData
  | URLSearchParams
  | Blob
  | ArrayBuffer
  | undefined;

export interface HttpRequestOptions {
  method?: HttpMethod;
  headers?: Record<string, string>;
  body?: RequestBody;
  query?: QueryParams;
  auth?: boolean;
  signal?: AbortSignal;
  credentials?: "include" | "omit" | "same-origin";
  unwrapData?: boolean;
}

export class HttpError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(
    message: string,
    options: { status: number; code?: string; details?: unknown },
  ) {
    super(message);
    this.name = "HttpError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
  }
}

function isAbsoluteUrl(path: string) {
  return /^https?:\/\//i.test(path);
}

function isApiEnvelope<T>(value: unknown): value is ApiEnvelope<T> {
  return Boolean(value) && typeof value === "object" && "data" in (value as object);
}

function buildUrl(path: string, query?: QueryParams) {
  const normalizedPath = isAbsoluteUrl(path)
    ? path
    : `${appEnv.apiBaseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
  const url = new URL(normalizedPath, window.location.origin);

  Object.entries(query || {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  return isAbsoluteUrl(normalizedPath)
    ? url.toString()
    : `${url.pathname}${url.search}${url.hash}`;
}

function normalizeBody(body: RequestBody, headers: Headers): NormalizedRequestBody {
  if (
    body == null ||
    typeof body === "string" ||
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    body instanceof ArrayBuffer
  ) {
    return body == null
      ? undefined
      : (body as Exclude<NormalizedRequestBody, undefined>);
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return JSON.stringify(body);
}

async function parseResponse(response: Response) {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

function getErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "message" in payload) {
    const message = (payload as ApiErrorPayload).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }

  return fallback;
}

export async function http<T>(
  path: string,
  options: HttpRequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const session = getAuthSession();

  if (options.auth !== false && session?.accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  }

  const requestInit = {
    method: options.method || "GET",
    headers,
    body: normalizeBody(options.body, headers),
    signal: options.signal,
    credentials: options.credentials || "include",
  };

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), requestInit);
  } catch (error) {
    throw new HttpError("网络请求失败，请检查后端服务是否已启动", {
      status: 0,
      details: error,
    });
  }

  const payload = await parseResponse(response);

  if (!response.ok) {
    throw new HttpError(
      getErrorMessage(payload, response.statusText || "请求失败"),
      {
        status: response.status,
        code:
          payload && typeof payload === "object" && "code" in payload
            ? (payload as ApiErrorPayload).code
            : undefined,
        details: payload,
      },
    );
  }

  if (options.unwrapData !== false && isApiEnvelope<T>(payload)) {
    return payload.data;
  }

  return payload as T;
}
