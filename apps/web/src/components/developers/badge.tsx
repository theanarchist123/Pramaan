"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { API_URL } from "@/lib/api";
import { CodeBlock } from "./code";

export function BadgeGenerator() {
  const [code, setCode] = useState("");
  const [site, setSite] = useState("");

  useEffect(() => {
    setSite(window.location.origin);
    fetch(`${API_URL}/v1/transparency?limit=1`).then((r) => r.json()).then((l) => l[0] && setCode(l[0].certificate_code)).catch(() => {});
  }, []);

  const c = code.trim().toUpperCase();
  const img = `${API_URL}/v1/badge/certificate/${c || "PRM-XXXXXXXXXX"}.svg`;
  const link = `${site}/verify/${c || "PRM-XXXXXXXXXX"}`;

  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="badge-code">Certificate code</label>
        <Input id="badge-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="PRM-XXXXXXXXXX" className="h-10 font-mono uppercase" />
        <p className="mt-2 text-sm text-muted-foreground">
          The badge is drawn live from the certificate&apos;s real status, so a revoked or unknown certificate can never keep showing a green tick.
        </p>
        <div className="mt-6 rounded-2xl border border-border bg-card p-6">
          <p className="mb-3 text-xs uppercase tracking-wide text-muted-foreground">Preview</p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {c ? <a href={link}><img src={img} alt={`Verified by Pramaan: ${c}`} height={22} /></a> : <p className="text-sm text-muted-foreground">Enter a code.</p>}
        </div>
      </div>
      <div className="space-y-4">
        <div>
          <p className="mb-1 text-sm font-medium">HTML</p>
          <CodeBlock language="html" code={`<a href="${link}">\n  <img src="${img}" alt="Verified by Pramaan" height="22">\n</a>`} />
        </div>
        <div>
          <p className="mb-1 text-sm font-medium">Markdown</p>
          <CodeBlock language="md" code={`[![Verified by Pramaan](${img})](${link})`} />
        </div>
      </div>
    </div>
  );
}
