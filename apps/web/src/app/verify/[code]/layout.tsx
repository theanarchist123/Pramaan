import type { Metadata } from "next";
import { API_URL } from "@/lib/api";

/** What a shared certificate link looks like in WhatsApp, LinkedIn and X. The words come from the server's verdict (I-9): "valid" only when the server says so. */
export async function generateMetadata({ params }: { params: Promise<{ code: string }> }): Promise<Metadata> {
  const { code } = await params;
  const v = await fetch(`${API_URL}/v1/verify/${encodeURIComponent(code)}`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  const name: string | undefined = v?.payload?.full_name;
  return {
    title: name ? `Certificate for ${name}` : "Check a Pramaan certificate",
    description: v?.valid
      ? `This certificate was issued to ${name} and has not changed since. Open it to see how each achievement was checked.`
      : "Open the link to check whether this certificate is genuine and unchanged.",
  };
}

export default function VerifyLayout({ children }: { children: React.ReactNode }) {
  return children;
}
