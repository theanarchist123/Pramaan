"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CertificateData } from "@/components/certificate/certificate";

export interface CertificateDetail {
  code: string;
  digest: string;
  signature: string;
  key_id: string;
  art_seed: string;
  photo_id: string;
  issued_at: string;
  revoked: boolean;
  payload: { redacted?: boolean; full_name?: string; claims?: { field: string; value: string; status: string }[]; issued_at?: string };
  profile: { slug: string; full_name: string; headline: string; sector: string; state: string } | null;
}

export interface VerifyResult {
  valid: boolean;
  code: string;
  reason: string;
  revoked: boolean;
  digest: string;
  key_id: string;
  issued_at: string;
  chain_ok: boolean;
  signature_ok: boolean;
  signature: string;
  public_key: string;
  log_position: number | null;
  log_size: number;
  entry_hash: string;
  changed_fields: string[];
  payload: CertificateDetail["payload"] | null;
}

export function toCertificateData(d: CertificateDetail): CertificateData | null {
  if (d.payload.redacted || !d.payload.full_name) return null;
  return {
    code: d.code,
    full_name: d.payload.full_name,
    claims: d.payload.claims ?? [],
    issued_at: d.payload.issued_at ?? d.issued_at,
    digest: d.digest,
    key_id: d.key_id,
    photo_id: d.photo_id,
    sector: d.profile?.sector,
    state: d.profile?.state,
  };
}

export function useCertificate(code: string, withVerify = false) {
  const [detail, setDetail] = useState<CertificateDetail | null>(null);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api<CertificateDetail>(`/v1/certificates/${encodeURIComponent(code)}`, { auth: false })
      .then((d) => alive && setDetail(d))
      .catch(() => alive && setError("not_found"));
    if (withVerify) {
      api<VerifyResult>(`/v1/verify/${encodeURIComponent(code)}`, { auth: false })
        .then((v) => alive && setVerify(v))
        .catch(() => alive && setError("unreachable"));
    }
    return () => {
      alive = false;
    };
  }, [code, withVerify]);

  return { detail, verify, error };
}
