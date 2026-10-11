import { readFile } from "node:fs/promises";
import { buildApp, MemoryObservationStore } from "../oracle/src/index.js";

// Only for the local failure test. Every container has its own verified sensor store.
const fixture = JSON.parse(await readFile("/job/fixture.json", "utf8"));
const app = buildApp({ store: new MemoryObservationStore(), policySource: fixture.policySource,
  adminToken: "local-fixture-admin", oracleToken: "local-fixture-oracle",
  now: () => new Date(fixture.now) });
for (const sensor of fixture.sensors) {
  const r = await app.inject({ method: "POST", url: "/v1/sensors",
    headers: { "x-admin-token": "local-fixture-admin" }, payload: sensor });
  if (r.statusCode !== 201) throw new Error(r.body);
}
for (const observation of fixture.observations) {
  const r = await app.inject({ method: "POST", url: "/v1/observations", payload: observation });
  if (r.statusCode !== 202) throw new Error(r.body);
}
await app.listen({ host: "0.0.0.0", port: 3000 });
