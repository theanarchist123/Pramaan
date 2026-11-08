"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CodeBlock } from "./code";

const TABS = ["PowerShell", "curl", "Python", "TypeScript", "MCP (AI agents)", "Webhooks"] as const;

export function Quickstart() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("curl");
  // On Windows, `curl` in PowerShell is an alias for Invoke-WebRequest and `\` is not a line continuation,
  // so the bash snippet fails there: open on the PowerShell tab instead.
  useEffect(() => {
    if (/win/i.test(navigator.platform) || /windows/i.test(navigator.userAgent)) setTab("PowerShell");
  }, []);
  const snippets: Record<(typeof TABS)[number], { language: string; code: string; note: string }> = {
    PowerShell: {
      language: "powershell",
      note: "For Windows PowerShell (its `curl` is a different command, so use Invoke-RestMethod). Public endpoints need no key; add X-API-Key for writes, webhooks and higher limits.",
      code: `# Is this certificate genuine?
Invoke-RestMethod ${API_URL}/v1/verify/PRM-ABCDEFGHJK

# Ask in plain English (any language)
$body = @{ query = "clean-energy innovators in Karnataka"; limit = 3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri ${API_URL}/v1/search -ContentType "application/json" -Body $body

# Authenticated
Invoke-RestMethod -Uri ${API_URL}/v1/profiles/mine -Headers @{ "X-API-Key" = "pk_live_..." }`,
    },
    curl: {
      language: "bash",
      note: "For macOS, Linux, Git Bash or WSL. (In Windows PowerShell use the PowerShell tab, or call curl.exe.) Public endpoints need no key; add X-API-Key for writes, webhooks and higher limits.",
      code: `# Is this certificate genuine?
curl ${API_URL}/v1/verify/PRM-ABCDEFGHJK

# Ask in plain English (any language)
curl -X POST ${API_URL}/v1/search \\
  -H "Content-Type: application/json" \\
  -d '{"query": "clean-energy innovators in Karnataka", "limit": 3}'

# Authenticated
curl -H "X-API-Key: pk_live_..." ${API_URL}/v1/profiles/mine`,
    },
    Python: {
      language: "python",
      note: "pip install ./packages/sdk/python — sync and async clients, typed errors, webhook verifier.",
      code: `from pramaan import Pramaan, verify_webhook

p = Pramaan(base_url="${API_URL}")                  # api_key="pk_live_..." for writes

v = p.verify("PRM-ABCDEFGHJK")
print(v["valid"], v["reason"])

for hit in p.search("clean-energy innovators in Karnataka")["results"]:
    print(hit["full_name"], "-", hit["reasons"])

# Try to forge it: the API names exactly what changed
check = p.check_payload("PRM-ABCDEFGHJK", {**v["payload"], "full_name": "Someone Else"})
print(check["valid"], check["changed_fields"])      # False ['full_name']`,
    },
    TypeScript: {
      language: "typescript",
      note: "Zero dependencies: uses fetch + Web Crypto. Types for every endpoint are generated from our OpenAPI schema.",
      code: `import { Pramaan, verifyWebhook } from "@pramaan/sdk";

const p = new Pramaan({ baseUrl: "${API_URL}" });   // apiKey: "pk_live_..." for writes

const v = await p.verify("PRM-ABCDEFGHJK");
console.log(v.valid, v.reason);

const { results } = await p.search("clean-energy innovators in Karnataka");
results.forEach((h) => console.log(h.full_name, h.reasons));

const check = await p.checkPayload("PRM-ABCDEFGHJK", { ...v.payload!, full_name: "Someone Else" });
console.log(check.valid, check.changed_fields);     // false [ 'full_name' ]`,
    },
    "MCP (AI agents)": {
      language: "json",
      note: "Let Claude Desktop, Cursor or any MCP client search the registry and verify documents. Add to the client's config:",
      code: `{
  "mcpServers": {
    "pramaan": {
      "command": "python",
      "args": ["<repo>/mcp/server.py"],
      "env": { "PRAMAAN_API_URL": "${API_URL}" }
    }
  }
}
// Tools: search_registry · get_profile · verify_certificate
//        check_document_content · registry_overview`,
    },
    Webhooks: {
      language: "python",
      note: "Create a webhook in the Webhooks tab, then verify every delivery with the signing secret. Use the RAW body.",
      code: `from pramaan import verify_webhook

@app.post("/hooks/pramaan")
async def hook(request: Request):
    body = await request.body()                       # raw bytes, not re-serialised JSON
    if not verify_webhook(SECRET, request.headers["X-Pramaan-Signature"], body):
        return Response(status_code=400)              # tampered, wrong secret, or a replay
    event = json.loads(body)                          # {"id", "event", "data", "created_at"}
    if event["event"] == "certificate.issued":
        ...

# Header format:  X-Pramaan-Signature: t=<unix>,v1=<hmac_sha256(secret, f"{t}.{body}")>
# Failed deliveries retry 3 times; every attempt is visible in the Webhooks tab.`,
    },
  };
  const s = snippets[tab];
  return (
    <div>
      <div role="tablist" className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm transition-colors",
              tab === t ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>
      <p className="mt-3 text-sm text-muted-foreground">{s.note}</p>
      <CodeBlock className="mt-3" code={s.code} language={s.language} />
    </div>
  );
}
