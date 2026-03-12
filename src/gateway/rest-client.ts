// src/gateway/rest-client.ts

export type RestClientOptions = {
  url: string;
  token?: string;
  timeoutMs?: number;
};

type EndpointMapping = {
  endpoint: string;
  type: string;
  body?: unknown;
};

export class RestClient {
  private baseUrl: string;
  private token?: string;
  private timeoutMs: number;

  constructor(options: RestClientOptions) {
    this.baseUrl = options.url.replace(/\/$/, "");
    this.token = options.token;
    this.timeoutMs = options.timeoutMs ?? 10_000;
  }

  async request<T>(
    method: string,
    params?: unknown,
    options?: { signal?: AbortSignal },
  ): Promise<T> {
    const { endpoint, type, body } = this.mapMethodToEndpoint(method, params);

    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    if (options?.signal) {
      options.signal.addEventListener("abort", () => {
        clearTimeout(timeoutId);
        controller.abort();
      });
    }

    try {
      const response = await fetch(url, {
        method: type,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(
          `REST Request to ${url} failed: ${response.status} ${response.statusText} - ${text}`,
        );
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(`Request timed out after ${this.timeoutMs}ms`, { cause: err });
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private mapMethodToEndpoint(method: string, params: unknown): EndpointMapping {
    switch (method) {
      case "health":
        return { endpoint: "/v1/system/status", type: "GET" };
      case "channels.status":
        return { endpoint: "/v1/channels", type: "GET", body: undefined };
      case "doctor.memory.status":
        return { endpoint: "/v1/doctor/memory", type: "GET", body: undefined };

      case "agent": {
        const input = params as { message?: string; agentId?: string } | undefined;
        return {
          endpoint: "/v1/chat/completions",
          type: "POST",
          body: {
            messages: [{ role: "user", content: input?.message ?? "Hello" }],
            model: "default",
            stream: false,
          },
        };
      }

      default:
        throw new Error(`Method '${method}' is not supported by the Python REST Client adapter.`);
    }
  }
}
