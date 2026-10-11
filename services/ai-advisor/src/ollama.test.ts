import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { expect, it } from "vitest";
import { OllamaProvider, ModelError } from "./ollama.js";
import { selectionSchema } from "./schemas.js";
import { z } from "zod";

const digest = `sha256:${"a".repeat(64)}`;
const request = { system: "fixture", user: "synthetic fixture", format: z.toJSONSchema(selectionSchema),
  options: { temperature: 0, seed: 42, num_ctx: 4096, num_predict: 512 }, think: false } as const;
const withServer = async (
  handler: (req: IncomingMessage, res: ServerResponse) => void,
  test: (provider: OllamaProvider) => Promise<void>
) => {
  const server = createServer(handler);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No test listener");
  try { await test(new OllamaProvider("fixture-only:1", `http://127.0.0.1:${address.port}`)); }
  finally { server.closeAllConnections(); await new Promise<void>((resolve) => server.close(() => resolve())); }
};
const json = (res: ServerResponse, value: unknown) => {
  res.setHeader("content-type", "application/json"); res.end(JSON.stringify(value));
};
const metadata = (req: IncomingMessage, res: ServerResponse, tagDigest = digest): boolean => {
  if (req.url === "/api/tags") { json(res, { models: [{ name: "fixture-only:1", digest: tagDigest }] }); return true; }
  if (req.url === "/api/version") { json(res, { version: "fixture-runtime" }); return true; }
  return false;
};
it("uses a bounded non-streaming schema request and records runtime and model digest", async () => {
  await withServer((req, res) => {
    if (metadata(req, res, digest.slice(7))) return;
    let body = ""; req.on("data", (chunk) => { body += String(chunk); });
    req.on("end", () => {
      const payload = JSON.parse(body);
      expect(payload.stream).toBe(false); expect(payload.think).toBe(false);
      expect(payload.options.temperature).toBe(0); expect(payload.format).toEqual(request.format);
      json(res, { model: "fixture-only:1", done: true, done_reason: "stop", message: { role: "assistant", content: "{}" } });
    });
  }, async (provider) => {
    const result = await provider.generate(request, new AbortController().signal);
    expect(result.modelDigest).toBe(digest); expect(result.runtimeVersion).toBe("fixture-runtime");
  });
});
it("rejects a model changed between metadata and inference", async () => {
  let tags = 0;
  await withServer((req, res) => {
    if (req.url === "/api/tags") tags += 1;
    if (metadata(req, res, tags > 1 ? `sha256:${"b".repeat(64)}` : digest)) return;
    json(res, { model: "fixture-only:1", done: true, done_reason: "stop", message: { role: "assistant", content: "{}" } });
  }, async (provider) => {
    await expect(provider.generate(request, new AbortController().signal)).rejects.toMatchObject({ code: "MODEL_CHANGED_DURING_REQUEST" });
  });
});
it("refuses a tag that no longer matches the approved digest before inference", async () => {
  await withServer((req, res) => { metadata(req, res); }, async (provider) => {
    const pinned = new OllamaProvider(provider.model, provider.endpoint, `sha256:${"b".repeat(64)}`);
    await expect(pinned.generate(request, new AbortController().signal)).rejects.toMatchObject({ code: "MODEL_DIGEST_MISMATCH" });
  });
});
it("rejects output stopped by token limit", async () => {
  await withServer((req, res) => {
    if (metadata(req, res)) return;
    json(res, { model: "fixture-only:1", done: true, done_reason: "length", message: { role: "assistant", content: "{}" } });
  }, async (provider) => {
    await expect(provider.generate(request, new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_MODEL_RESPONSE" });
  });
});
it("rejects oversized HTTP bodies before JSON parsing", async () => {
  await withServer((_req, res) => { res.end("x".repeat(300_000)); }, async (provider) => {
    await expect(provider.generate(request, new AbortController().signal)).rejects.toMatchObject({ code: "MODEL_RESPONSE_TOO_LARGE" });
  });
});
it("does not follow redirects to another inference server", async () => {
  await withServer((_req, res) => { res.writeHead(302, { location: "http://example.com" }); res.end(); }, async (provider) => {
    await expect(provider.generate(request, new AbortController().signal)).rejects.toBeInstanceOf(ModelError);
  });
});
it("rejects cloud endpoints, credentials and endpoint paths", () => {
  for (const endpoint of ["https://api.example.com", "http://localhost:11434", "http://127.0.0.1/path", "http://user:secret@127.0.0.1"]) {
    expect(() => new OllamaProvider("fixture-only:1", endpoint)).toThrow();
  }
});
