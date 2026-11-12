import type { Profile } from "@/lib/types";

/** Where a profile is in its journey. Derived only from the server's `status` and `decision_basis`; never from free text (I-9). */
export type StageKey = "tell" | "submitted" | "decided";

export interface Stage {
  key: StageKey;
  label: string;
  /** done = finished, current = where they are, todo = ahead */
  state: "done" | "current" | "todo";
  note?: string;
}

export function stagesOf(p: Pick<Profile, "status" | "decision_basis" | "claims">): Stage[] {
  const hasClaims = p.claims.length > 0;
  const tell: Stage = { key: "tell", label: "Tell us about yourself", state: p.status === "draft" || p.status === "rejected" ? "current" : "done", note: hasClaims ? `${p.claims.length} on your profile` : undefined };
  const submitted: Stage = { key: "submitted", label: "Checks and review", state: p.status === "pending_review" ? "current" : p.status === "approved" || p.status === "suspended" ? "done" : "todo" };
  let decided: Stage;
  if (p.status === "approved") {
    decided = {
      key: "decided",
      label: "Verified",
      state: "done",
      note: p.decision_basis === "reviewer" ? "Approved by a person" : p.decision_basis === "automation" ? "Passed automated checks" : undefined,
    };
  } else if (p.status === "suspended") {
    decided = { key: "decided", label: "Suspended", state: "current", note: "The registry has taken this profile down for now. Contact the registry for the reason." };
  } else if (p.status === "rejected") {
    decided = { key: "decided", label: "Needs changes", state: "current", note: "Edit and send it again" };
  } else {
    decided = { key: "decided", label: "Verified", state: "todo" };
  }
  return [tell, submitted, decided];
}
