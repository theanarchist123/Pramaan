"use client";

import { use } from "react";
import { Certificate } from "@/components/certificate/certificate";
import { toCertificateData, useCertificate } from "@/hooks/use-certificate";

// Print route: the bare certificate at its native size. Headless Chromium renders this to PDF/PNG.
export default function CertificatePrintPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const { detail, error } = useCertificate(code);
  const data = detail ? toCertificateData(detail) : null;

  if (error || (detail && !data)) return <p className="p-10">Certificate unavailable.</p>;
  return (
    <div data-print-route style={{ width: 1123, height: 794, background: "white" }}>
      <h1 className="sr-only">Certificate {code}</h1>
      {data && <Certificate data={data} />}
    </div>
  );
}
