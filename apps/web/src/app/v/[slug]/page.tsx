"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { asEntries, resolvePath, safeBlocks, type Block, type ViewSpec } from "@/lib/viewspec";

/** A page the registry's designer agent proposed and two people approved. It is DATA drawn by this fixed interpreter: no script, markup or link from the spec ever reaches the page. */
export default function ViewPage() {
  const { slug } = useParams<{ slug: string }>();
  const [spec, setSpec] = useState<ViewSpec | null>(null);
  const [missing, setMissing] = useState(false);
  const [data, setData] = useState<Record<string, unknown>>({});

  useEffect(() => {
    api<{ spec: ViewSpec }>(`/v1/views/${encodeURIComponent(slug)}`).then((r) => setSpec(r.spec)).catch(() => setMissing(true));
  }, [slug]);

  const blocks = spec ? safeBlocks(spec) : [];
  useEffect(() => {
    const endpoints = Array.from(new Set(blocks.flatMap((b) => ("bind" in b ? [b.bind.endpoint] : []))));
    endpoints.forEach((e) => api<unknown>(e).then((d) => setData((p) => ({ ...p, [e]: d }))).catch(() => setData((p) => ({ ...p, [e]: null }))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec]);

  if (missing) return <div className="mx-auto max-w-3xl px-4 py-16"><h1 className="text-3xl font-semibold">Page not found</h1><p className="mt-2 text-muted-foreground">This page does not exist, or has not been published.</p></div>;
  if (!spec) return <div className="mx-auto max-w-3xl px-4 py-16 text-muted-foreground">Loading…</div>;
  const cols = spec.layout === "grid3" ? "md:grid-cols-3" : spec.layout === "grid2" ? "md:grid-cols-2" : "";
  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-4xl font-semibold">{String(spec.title).slice(0, 120)}</h1>
      <div className={`mt-8 grid gap-6 ${cols}`}>{blocks.map((b, i) => <BlockView key={i} b={b} data={data} />)}</div>
    </div>
  );
}

function BlockView({ b, data }: { b: Block; data: Record<string, unknown> }) {
  if (b.type === "heading") return b.level === 1 ? <h1 className="text-3xl font-semibold md:col-span-full">{b.text}</h1> : b.level === 3 ? <h3 className="text-lg font-semibold md:col-span-full">{b.text}</h3> : <h2 className="text-2xl font-semibold md:col-span-full">{b.text}</h2>;
  if (b.type === "text") return <p className="text-base leading-relaxed text-muted-foreground md:col-span-full">{b.text}</p>;
  const raw = data[b.bind.endpoint];
  const value = raw === undefined ? undefined : resolvePath(raw, b.bind.path);
  const card = "rounded-2xl border border-border bg-card p-5";
  if (value === undefined) return <div className={card}><p className="text-sm text-muted-foreground">{b.type === "table" ? b.columns.join(" / ") : b.label}: loading…</p></div>;
  if (b.type === "stat") return <div className={card}><p className="text-sm text-muted-foreground">{b.label}</p><p className="mt-1 text-4xl font-semibold">{typeof value === "number" || typeof value === "string" ? String(value) : "—"}</p></div>;
  const entries = asEntries(value);
  if (b.type === "bar_chart") {
    const max = Math.max(1, ...entries.map(([, v]) => Number(v) || 0));
    return (
      <div className={card}>
        <p className="font-medium">{b.label}</p>
        <ul className="mt-3 space-y-1.5">
          {entries.slice(0, 20).map(([k, v]) => (
            <li key={k} className="grid grid-cols-[8rem_1fr_3rem] items-center gap-2 text-sm">
              <span className="truncate">{k}</span>
              <span className="h-3 rounded bg-primary/70" style={{ width: `${((Number(v) || 0) / max) * 100}%` }} aria-hidden="true" />
              <span className="text-right tabular-nums">{String(v)}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (b.type === "table") {
    return (
      <div className={`${card} overflow-x-auto`}>
        <table className="w-full text-sm"><thead><tr>{b.columns.slice(0, 4).map((c) => <th key={c} className="py-1 text-left font-medium">{c}</th>)}</tr></thead>
          <tbody>{entries.slice(0, 50).map(([k, v]) => <tr key={k} className="border-t border-border"><td className="py-1">{k}</td><td className="py-1">{String(v)}</td></tr>)}</tbody></table>
      </div>
    );
  }
  return <div className={card}><p className="font-medium">{b.label}</p><ul className="mt-2 list-disc pl-5 text-sm">{entries.slice(0, 30).map(([k, v]) => <li key={k}>{String(v)}</li>)}</ul></div>;
}
