"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { paletteFor } from "@/lib/certificate-art";
import { Guilloche, Rosette } from "@/components/certificate/art";
import { LogoMark } from "@/components/logo";

export const CERT_W = 1123;
export const CERT_H = 794;

export interface CertificateData {
  code: string;
  full_name: string;
  claims: { field: string; value: string; status: string }[];
  issued_at: string;
  digest: string;
  key_id: string;
  photo_id: string;
  sector?: string | null;
  state?: string | null;
}

const STATUS_LABEL: Record<string, string> = {
  document: "Document verified",
  web: "Public evidence",
  human: "Confirmed by a reviewer",
  issuer: "Verified by issuer",
};
// "Independently" is only true when every printed claim is backed by a document or the issuer itself (invariant I-9).
const INDEPENDENT = new Set(["document", "issuer"]);

function formatDate(iso: string) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
}

/**
 * The certificate itself: fixed A4-landscape canvas (1123×794). Always light (it is a printed
 * document), regardless of the app theme. `data-cert-ready` tells the PDF renderer when images loaded.
 */
export function Certificate({ data, forceTamper = false }: { data: CertificateData; forceTamper?: boolean }) {
  const palette = paletteFor(data.sector);
  const [photoDone, setPhotoDone] = useState(!data.photo_id);
  const [qrDone, setQrDone] = useState(false);

  useEffect(() => {
    setPhotoDone(!data.photo_id);
    setQrDone(false);
  }, [data.photo_id, data.code]);

  const photo = data.photo_id
    ? `/certificate-photos/${encodeURIComponent(data.photo_id)}.jpg` // self-hosted: a credential must not depend on a third party
    : "";
  const shown = data.claims.slice(0, 4);

  return (
    <div
      id="certificate"
      data-cert-ready={photoDone && qrDone}
      style={{
        width: CERT_W,
        height: CERT_H,
        background: "linear-gradient(135deg,#fdf9ef 0%,#f7efdc 100%)",
        color: "#1b1a17",
        position: "relative",
        overflow: "hidden",
        fontFamily: "var(--font-inter), var(--font-deva), sans-serif",
        WebkitPrintColorAdjust: "exact",
        printColorAdjust: "exact",
      }}
    >
      {/* texture: guilloche behind the text */}
      <div style={{ position: "absolute", left: -90, top: 120, opacity: 0.55 }}>
        <Guilloche seed={data.digest} sector={data.sector} size={640} />
      </div>

      {/* frames */}
      <div style={{ position: "absolute", inset: 20, border: `2px solid ${palette.ink}`, borderRadius: 6 }} />
      <div style={{ position: "absolute", inset: 29, border: `1px solid ${palette.primary}`, borderRadius: 3 }} />
      {[
        { left: 14, top: 14 }, { right: 14, top: 14 }, { left: 14, bottom: 14 }, { right: 14, bottom: 14 },
      ].map((pos, i) => (
        <div key={i} style={{ position: "absolute", ...pos, background: "#fbf6ea", borderRadius: 999, padding: 2 }}>
          <Rosette seed={data.digest} sector={data.sector} size={30} salt={i + 1} />
        </div>
      ))}

      {/* arched window with the sector photo (a jharokha) */}
      <div
        style={{
          position: "absolute", right: 56, top: 62, bottom: 62, width: 318,
          borderRadius: "159px 159px 8px 8px", overflow: "hidden",
          border: `3px solid ${palette.ink}`, background: palette.ink,
        }}
      >
        {photo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photo}
            alt=""
            onLoad={() => setPhotoDone(true)}
            onError={() => setPhotoDone(true)}
            style={{ width: "100%", height: "100%", objectFit: "cover", filter: "saturate(0.85) contrast(1.05)" }}
          />
        )}
        {/* Plain alpha tint (no mix-blend-mode: it fails to paint inside the 3D-tilt container). */}
        <div style={{ position: "absolute", inset: 0, background: `linear-gradient(180deg, ${palette.primary}26 0%, ${palette.ink}8c 100%)` }} />
        <div style={{ position: "absolute", inset: 0, background: `radial-gradient(circle at 50% 110%, ${palette.ink}b3, transparent 60%)` }} />
      </div>

      {/* the seal: the art IS the fingerprint of this exact content */}
      <div style={{ position: "absolute", right: 150, bottom: 40, background: "#fbf6ea", borderRadius: 999, padding: 6, boxShadow: `0 0 0 2px ${palette.ink}` }}>
        <Rosette seed={data.digest} sector={data.sector} size={134} />
      </div>

      {/* content */}
      <div style={{ position: "absolute", left: 84, top: 66, width: 600 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <LogoMark className="size-9" />
          <span className="font-display" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "0.02em" }}>Pramaan</span>
        </div>
        <p style={{ marginTop: 26, fontSize: 12, letterSpacing: "0.32em", textTransform: "uppercase", color: palette.ink, fontWeight: 600 }}>
          Certificate of Verified Achievement
        </p>
        <p style={{ marginTop: 26, fontSize: 15, color: "#6b6558" }}>This certifies that</p>
        <h2
          className="font-display"
          style={{ marginTop: 4, fontSize: data.full_name.length > 24 ? 44 : 56, lineHeight: 1.05, fontWeight: 600, color: "#1b1a17" }}
        >
          {data.full_name}
        </h2>
        <p style={{ marginTop: 8, fontSize: 14, color: "#6b6558" }}>
          {[data.sector, data.state].filter(Boolean).join(" · ")}
        </p>
        <div style={{ margin: "22px 0 14px", height: 1, background: `linear-gradient(90deg, ${palette.ink}, transparent)` }} />
        <p style={{ fontSize: 14, color: "#4a463d" }}>
          {data.claims.length > 0 && data.claims.every((x) => INDEPENDENT.has(x.status))
            ? "has had the following achievements independently verified:"
            : "has the following achievements on record, each shown with how it was checked:"}
        </p>
        <ul style={{ marginTop: 12, display: "grid", gap: 9 }}>
          {shown.map((c, i) => (
            <li key={i} style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
              <span style={{ width: 7, height: 7, background: palette.primary, transform: "rotate(45deg)", flexShrink: 0, translate: "0 -1px" }} />
              <span style={{ fontSize: 15, lineHeight: 1.3 }}>
                {c.value}{" "}
                <span style={{ fontSize: 12.5, color: palette.ink, fontWeight: 600 }}>
                  · {STATUS_LABEL[c.status] ?? c.status}
                </span>
              </span>
            </li>
          ))}
          {data.claims.length > shown.length && (
            <li style={{ fontSize: 12, color: "#6b6558", marginLeft: 17 }}>+ {data.claims.length - shown.length} more on the verification page</li>
          )}
        </ul>
      </div>

      {/* footer: meta + QR */}
      <div style={{ position: "absolute", left: 84, bottom: 54, width: 600, display: "flex", alignItems: "flex-end", gap: 22 }}>
        <div style={{ background: "#fffdf7", padding: 7, border: `1px solid ${palette.ink}55`, borderRadius: 6 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${API_URL}/v1/certificates/${data.code}/qr.svg`}
            alt={`QR code to verify certificate ${data.code}`}
            width={92}
            height={92}
            onLoad={() => setQrDone(true)}
            onError={() => setQrDone(true)}
            style={{ display: "block" }}
          />
        </div>
        <div style={{ fontSize: 11, lineHeight: 1.65, color: "#4a463d" }}>
          <p style={{ fontWeight: 600, color: palette.ink, letterSpacing: "0.04em" }}>Scan to verify — or try to forge it.</p>
          <p>Issued {formatDate(data.issued_at)}</p>
          <p>
            Certificate <span style={{ fontFamily: "ui-monospace, monospace" }}>{data.code}</span>
          </p>
          <p style={{ fontFamily: "ui-monospace, monospace", fontSize: 9.5, color: "#7a7467" }}>
            sha-256 {data.digest.slice(0, 24)}… · Ed25519 key {data.key_id}
          </p>
        </div>
      </div>

      {forceTamper && (
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", background: "rgba(180,30,30,0.08)" }}>
          <div style={{ transform: "rotate(-12deg)", border: "6px solid #b42318", color: "#b42318", padding: "10px 30px", fontSize: 56, fontWeight: 800, letterSpacing: "0.1em", background: "rgba(255,255,255,0.7)" }}>
            NOT VALID
          </div>
        </div>
      )}
    </div>
  );
}
