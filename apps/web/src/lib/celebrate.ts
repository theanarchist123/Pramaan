/**
 * The certificate-issued celebration (motion V-08). Call it ONLY after the server has confirmed the certificate (invariant I-9);
 * it is never driven by a timer. Skipped entirely when the viewer reduces motion. The library is loaded on demand.
 */
export async function celebrate(reduced: boolean): Promise<void> {
  if (reduced || typeof window === "undefined") return;
  const { default: base } = await import("canvas-confetti");
  // No web worker: the library would start one from a blob: address, which our Content-Security-Policy (rightly) refuses. The main thread is plenty for this.
  const confetti = base.create(undefined, { resize: true, useWorker: false });
  const colors = ["#FFB81C", "#14152B", "#0B7F57", "#2447C9", "#FFFFFF"];
  const shot = (x: number, angle: number) => confetti({ particleCount: 70, spread: 70, startVelocity: 48, angle, origin: { x, y: 0.75 }, colors, disableForReducedMotion: true });
  shot(0.1, 60);
  shot(0.9, 120);
  window.setTimeout(() => confetti({ particleCount: 90, spread: 110, origin: { x: 0.5, y: 0.6 }, colors, disableForReducedMotion: true }), 250);
}
