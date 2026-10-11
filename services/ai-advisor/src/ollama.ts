import { z } from "zod";
import type { AdvisorProvider, ModelRequest, ModelResult } from "./schemas.js";

export class ModelError extends Error {
  public constructor(public readonly code: string) { super(code); }
}
const digestSchema = z.string().regex(/^(sha256:)?[0-9a-f]{64}$/)
  .transform((value) => value.startsWith("sha256:") ? value : `sha256:${value}`);
const tagsSchema = z.object({ models: z.array(z.object({ name: z.string(), digest: digestSchema })) });
const versionSchema = z.object({ version: z.string().min(1).max(64) });
const chatSchema = z.object({
  model: z.string(), done: z.literal(true), done_reason: z.literal("stop"),
  message: z.object({ role: z.literal("assistant"), content: z.string().max(16_384) })
});

export class OllamaProvider implements AdvisorProvider {
  public readonly endpoint: string;
  public constructor(public readonly model: string, endpoint = "http://127.0.0.1:11434",
    private readonly expectedDigest?: string) {
    const url = new URL(endpoint);
    // Local-only first increment. No private data can be redirected to a remote backend.
    if (url.protocol !== "http:" || !["127.0.0.1", "[::1]"].includes(url.hostname) ||
        url.username || url.password || url.search || url.hash || url.pathname !== "/") {
      throw new Error("Ollama must use an explicit loopback HTTP endpoint");
    }
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}$/.test(model)) throw new Error("Invalid model name");
    if (expectedDigest !== undefined && !/^sha256:[0-9a-f]{64}$/.test(expectedDigest)) throw new Error("Invalid expected model digest");
    this.endpoint = url.origin;
  }
  private async json(path: string, signal: AbortSignal, body?: unknown): Promise<unknown> {
    const response = await fetch(`${this.endpoint}${path}`, {
      method: body === undefined ? "GET" : "POST", redirect: "error", signal,
      ...(body === undefined ? {} : {
        headers: { "content-type": "application/json" }, body: JSON.stringify(body)
      })
    });
    if (!response.ok) throw new ModelError(response.status === 404 ? "MODEL_UNAVAILABLE" : "MODEL_HTTP_ERROR");
    // Bound the streamed HTTP body before JSON parsing, including metadata responses.
    const reader = response.body?.getReader();
    if (!reader) throw new ModelError("INVALID_MODEL_RESPONSE");
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > 256 * 1024) throw new ModelError("MODEL_RESPONSE_TOO_LARGE");
        chunks.push(chunk.value);
      }
    } finally { await reader.cancel(); }
    try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
    catch { throw new ModelError("INVALID_MODEL_RESPONSE"); }
  }
  public async generate(request: ModelRequest, signal: AbortSignal): Promise<ModelResult> {
    try {
      const before = tagsSchema.parse(await this.json("/api/tags", signal));
      const tag = before.models.find((entry) => entry.name === this.model);
      if (!tag) throw new ModelError("MODEL_UNAVAILABLE");
      if (this.expectedDigest && tag.digest !== this.expectedDigest) throw new ModelError("MODEL_DIGEST_MISMATCH");
      const version = versionSchema.parse(await this.json("/api/version", signal));
      const chat = chatSchema.parse(await this.json("/api/chat", signal, {
        model: this.model, stream: false, think: request.think, format: request.format,
        messages: [{ role: "system", content: request.system }, { role: "user", content: request.user }],
        options: request.options, keep_alive: "5m"
      }));
      const after = tagsSchema.parse(await this.json("/api/tags", signal));
      if (after.models.find((entry) => entry.name === this.model)?.digest !== tag.digest) {
        throw new ModelError("MODEL_CHANGED_DURING_REQUEST");
      }
      return { content: chat.message.content, model: chat.model, modelDigest: tag.digest, runtimeVersion: version.version };
    } catch (error) {
      if (error instanceof ModelError) throw error;
      if (signal.aborted) throw new ModelError("MODEL_TIMEOUT");
      if (error instanceof z.ZodError) throw new ModelError("INVALID_MODEL_RESPONSE");
      throw new ModelError("MODEL_UNAVAILABLE");
    }
  }
}
