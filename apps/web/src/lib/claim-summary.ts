import type { Claim, ClaimStatus, Profile } from "@/lib/types";

/** Statuses that mean a person or document confirmed the claim. A public web quote alone is evidence, not confirmation. */
export const CONFIRMED: readonly ClaimStatus[] = ["document", "human", "issuer"];

export function summarise(claims: Claim[]) {
  const count = (s: ClaimStatus) => claims.filter((c) => c.status === s).length;
  const confirmed = claims.filter((c) => CONFIRMED.includes(c.status)).length;
  return { total: claims.length, confirmed, web: count("web"), self: count("self") };
}

/** One honest sentence about how the profile was decided, from the server enum only (I-9). */
export function decisionLine(p: Pick<Profile, "status" | "decision_basis">): string | null {
  if (p.status !== "approved") return null;
  if (p.decision_basis === "reviewer") return "Approved by a person who read the evidence.";
  if (p.decision_basis === "automation") return "Passed the registry's automated checks.";
  return null;
}
