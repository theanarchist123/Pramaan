# @pramaan/sdk — TypeScript SDK

Zero dependencies (platform `fetch` + Web Crypto). Node 18+, Deno, Bun, Workers, browsers.

```ts
import { Pramaan, verifyWebhook } from "@pramaan/sdk";

const p = new Pramaan({ baseUrl: "https://your-pramaan-host" });   // apiKey: "pk_live_…" for writes

const v = await p.verify("PRM-ABCDEFGHJK");
console.log(v.valid, v.reason);

const { results } = await p.search("clean-energy innovators in Karnataka");
results.forEach((h) => console.log(h.full_name, h.reasons));

// Try to forge it: the API names exactly what changed
const check = await p.checkPayload("PRM-ABCDEFGHJK", { ...v.payload!, full_name: "Someone Else" });
console.log(check.valid, check.changed_fields);   // false [ 'full_name' ]
```

**Webhooks** — verify with the RAW body:

```ts
app.post("/hooks/pramaan", express.raw({ type: "*/*" }), async (req, res) => {
  const ok = await verifyWebhook(process.env.PRAMAAN_SECRET!, req.get("X-Pramaan-Signature")!, req.body);
  if (!ok) return res.sendStatus(400);       // tampered, wrong secret, or a replay older than 5 minutes
  const event = JSON.parse(req.body.toString("utf-8"));
});
```

**Generated types.** `src/schema.d.ts` is generated from the server's own OpenAPI document, so types can't drift
from the API: start the API and run `npm run generate`. Errors are `PramaanError` (`.status`, `.detail`, `.retryAfter`).
