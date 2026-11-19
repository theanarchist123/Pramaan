import type { VerifyResult } from "@/hooks/use-certificate";

/** The five outcomes of checking a certificate (spec 6.4). The verdict comes from what the registry returned, never from guesswork. */
export type Verdict = "valid" | "replaced" | "revoked" | "altered" | "unconfirmed" | "not_found";

export function verdictOf(v: VerifyResult | null, notFound: boolean): Verdict {
  if (notFound || !v) return "not_found";
  if (v.revoked) return "revoked";
  // the registry lost a key: say so honestly instead of calling a genuine certificate edited
  if (!v.valid && v.reason?.startsWith("Signed with a key this registry no longer publishes")) return "unconfirmed";
  if (!v.valid) return "altered";
  if (v.superseded_by) return "replaced";
  return "valid";
}

export const VERDICT_COPY: Record<Verdict, { title: string; sentence: (v?: VerifyResult | null) => string; tone: "verified" | "caution" | "seal" | "neutral" }> = {
  valid: { title: "Authentic", sentence: () => "The content has not changed since it was issued.", tone: "verified" },
  replaced: {
    title: "Genuine, but replaced",
    sentence: (v) => `This certificate is genuine, but a newer one (${v?.superseded_by ?? ""}) has replaced it.`,
    tone: "caution",
  },
  revoked: { title: "Revoked", sentence: () => "The registry revoked this certificate. Do not rely on it.", tone: "seal" },
  altered: { title: "Does not match its signature", sentence: () => "This content differs from what was signed. It may have been edited.", tone: "seal" },
  unconfirmed: {
    title: "Cannot be confirmed right now",
    sentence: () => "The registry cannot check this signature at the moment. This is our problem, not a sign the certificate was edited. Please try again later.",
    tone: "caution",
  },
  not_found: { title: "Not found", sentence: () => "We have no certificate with this code. Treat the document as unverified.", tone: "neutral" },
};

/** Certificate codes never contain 0, 1, I, L, O or U. Offer the likely intended readings of a mistyped code. */
export const CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ";
const LOOKALIKES: Record<string, string> = { "0": "O", O: "0", "1": "I", I: "1", L: "1", U: "V" };
export function cleanChar(ch: string): string {
  return ch.toUpperCase().replace(/[^A-Z0-9]/g, "");
}
export function isCodeChar(ch: string): boolean {
  return CODE_ALPHABET.includes(ch.toUpperCase());
}
export function suggestions(code: string): string[] {
  const body = code.replace(/^PRM-/, "");
  const bad = [...body].findIndex((c) => !isCodeChar(c));
  if (bad < 0) return [];
  return [...new Set([LOOKALIKES[body[bad]], body[bad] === "0" ? "O" : undefined].filter(Boolean) as string[])]
    .filter((r) => isCodeChar(r))
    .map((r) => `PRM-${body.slice(0, bad)}${r}${body.slice(bad + 1)}`);
}
