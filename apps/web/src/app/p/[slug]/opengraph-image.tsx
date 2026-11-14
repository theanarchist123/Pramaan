import { ImageResponse } from "next/og";
import { API_URL } from "@/lib/api";

export const alt = "A verified profile on Pramaan";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** The preview card shown when a profile link is shared (WhatsApp, LinkedIn, X). Text only: no photo, no stock imagery. */
export default async function OgImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = await fetch(`${API_URL}/v1/profiles/${encodeURIComponent(slug)}`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  const name: string = p?.full_name ?? "Pramaan";
  const line: string = p ? [p.headline || p.sector, [p.city, p.state].filter(Boolean).join(", ")].filter(Boolean).join(" · ") : "India's verified registry of achievers";
  const confirmed: number = p ? p.claims.filter((c: { status: string }) => ["document", "issuer", "human"].includes(c.status)).length : 0;
  const total: number = p ? p.claims.length : 0;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#FFB81C", padding: 64, color: "#14152B" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 38, fontWeight: 800 }}>
          <div style={{ width: 52, height: 52, borderRadius: 16, background: "#14152B", color: "#FFB81C", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36 }}>✓</div>
          Pramaan
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: name.length > 22 ? 84 : 104, fontWeight: 800, lineHeight: 1.02 }}>{name}</div>
          <div style={{ marginTop: 20, fontSize: 40, fontWeight: 500 }}>{line}</div>
        </div>
        <div style={{ display: "flex", fontSize: 32, fontWeight: 700 }}>
          {total > 0 ? `${confirmed} of ${total} achievements confirmed by evidence` : "Don't claim it. Prove it."}
        </div>
      </div>
    ),
    size,
  );
}
