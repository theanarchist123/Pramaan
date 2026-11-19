import { ImageResponse } from "next/og";
import { API_URL } from "@/lib/api";

export const alt = "A certificate on Pramaan";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** The preview card for a shared certificate link. Text only (no photo, no stock imagery). It says "Authentic" only when the server says the certificate is valid (I-9);
 *  anything else is neutral, so a preview can never vouch for a certificate that failed its check. */
export default async function OgImage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const v = await fetch(`${API_URL}/v1/verify/${encodeURIComponent(code)}`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  const name: string = v?.payload?.full_name ?? "Pramaan certificate";
  const ok = Boolean(v?.valid) && !v?.revoked && !v?.superseded_by; // a replaced certificate is not previewed as simply authentic
  const claims: string[] = (v?.payload?.claims ?? []).slice(0, 2).map((c: { value: string }) => c.value);

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#14152B", padding: 64, color: "#FFFFFF" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 38, fontWeight: 800 }}>
          <div style={{ width: 52, height: 52, borderRadius: 16, background: "#FFB81C", color: "#14152B", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36 }}>✓</div>
          Pramaan
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 34, fontWeight: 600, color: "#FFB81C" }}>{ok ? "Authentic certificate" : "Certificate"}</div>
          <div style={{ marginTop: 10, fontSize: name.length > 22 ? 84 : 104, fontWeight: 800, lineHeight: 1.02 }}>{name}</div>
          {ok && claims.map((c) => (
            <div key={c} style={{ marginTop: 14, fontSize: 34, fontWeight: 500, opacity: 0.85 }}>{c.length > 70 ? `${c.slice(0, 67)}…` : c}</div>
          ))}
        </div>
        <div style={{ display: "flex", fontSize: 30, fontWeight: 700 }}>
          {ok ? `Checked against Pramaan's public log · ${code}` : `Open to check ${code}`}
        </div>
      </div>
    ),
    size,
  );
}
