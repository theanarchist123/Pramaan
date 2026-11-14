/** Plain-language labels for the Desk. The server's codes stay as they are (they are what is stored and audited); people read these. */

const REASONS: Record<string, string> = {
  low_confidence: "Low confidence",
  name_mismatch: "Name does not match the document",
  award_claim: "Award claim",
  duplicate_document: "Document already used",
  first_listing: "First public listing",
  namesake: "Same name as someone else",
  edited_after_approval: "Edited after approval",
  document_flagged: "Document flagged",
  needs_human: "Needs a person",
};

export function reasonLabel(code: string): string {
  if (REASONS[code]) return REASONS[code];
  const t = code.replace(/[_-]+/g, " ").trim().toLowerCase();
  return t ? t[0].toUpperCase() + t.slice(1) : code;
}

export type Tone = "ok" | "warn" | "bad" | "info" | "quiet";

/** A deadline as words plus a tone. Never colour alone: the text always says it. */
export function dueState(due: string | null, now = Date.now()): { text: string; tone: Tone; late: boolean } {
  if (!due) return { text: "No deadline", tone: "quiet", late: false };
  const ms = new Date(due).getTime() - now;
  const hours = Math.abs(ms) / 3_600_000;
  const span = hours < 1 ? `${Math.max(1, Math.round(hours * 60))} min` : hours < 48 ? `${Math.round(hours)} h` : `${Math.round(hours / 24)} days`;
  if (ms < 0) return { text: `Overdue by ${span}`, tone: "bad", late: true };
  return { text: `Due in ${span}`, tone: hours < 6 ? "warn" : "ok", late: false };
}

export const initials = (n: string) =>
  n.replace(/^(dr|prof|shri|smt)\.?\s+/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => Array.from(w)[0]).join("").toUpperCase() || "?";

/** A stable pastel pair (1 to 6) for a name or sector, so the same person is always the same colour. */
export function tileFor(key: string): number {
  let h = 0;
  for (const ch of key) h = (h * 31 + ch.codePointAt(0)!) % 997;
  return (h % 6) + 1;
}

export function greeting(d = new Date()): string {
  const h = d.getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}
