export interface Segment {
  text: string;
  /** true when this stretch of the message is the exact wording a fact was recorded from */
  captured: boolean;
}

/**
 * Split a message into plain and captured stretches. `phrases` are the exact quotes the server stored as the chat evidence for the facts it
 * recorded from this message. Matching is a literal, case-insensitive search for each quote in the message; a quote that is not found
 * is simply not marked (we never guess at what the model "meant"). Overlaps are merged, and very short quotes are ignored so a stray word
 * is not highlighted. Joining the segments always gives the original text back.
 */
export function markCaptured(text: string, phrases: string[]): Segment[] {
  const low = text.toLowerCase();
  const ranges: [number, number][] = [];
  for (const raw of phrases) {
    const p = raw.trim().toLowerCase();
    if (p.length < 4) continue;
    const at = low.indexOf(p);
    if (at >= 0) ranges.push([at, at + p.length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  const out: Segment[] = [];
  let pos = 0;
  for (const [a, b] of merged) {
    if (a > pos) out.push({ text: text.slice(pos, a), captured: false });
    out.push({ text: text.slice(a, b), captured: true });
    pos = b;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), captured: false });
  return out.length ? out : [{ text, captured: false }];
}
