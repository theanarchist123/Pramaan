"use client";

import { useEffect, useRef, useState } from "react";
import { CERT_H, CERT_W } from "@/components/certificate/certificate";

/** Scales the fixed-size certificate to its container and adds a pointer-driven 3D tilt + glare. */
export function ScaledTilt({ children, tilt = true }: { children: React.ReactNode; tilt?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.6);
  const [t, setT] = useState({ x: 0, y: 0, gx: 50, gy: 50, active: false });

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setScale(el.clientWidth / CERT_W));
    ro.observe(el);
    setScale(el.clientWidth / CERT_W);
    return () => ro.disconnect();
  }, []);

  const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function onMove(e: React.PointerEvent) {
    if (!tilt || reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    setT({ x: (0.5 - py) * 9, y: (px - 0.5) * 12, gx: px * 100, gy: py * 100, active: true });
  }

  return (
    <div style={{ perspective: 1400 }}>
      <div
        ref={box}
        onPointerMove={onMove}
        onPointerLeave={() => setT({ x: 0, y: 0, gx: 50, gy: 50, active: false })}
        className="relative w-full overflow-hidden rounded-xl shadow-2xl shadow-black/20 ring-1 ring-black/10"
        style={{
          height: CERT_H * scale,
          transform: `rotateX(${t.x}deg) rotateY(${t.y}deg)`,
          transition: t.active ? "transform 60ms linear" : "transform 500ms ease",
        }}
      >
        <div style={{ width: CERT_W, height: CERT_H, transform: `scale(${scale})`, transformOrigin: "top left" }}>{children}</div>
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            opacity: t.active ? 1 : 0,
            transition: "opacity 300ms",
            background: `radial-gradient(circle at ${t.gx}% ${t.gy}%, rgba(255,255,255,0.35), transparent 45%)`,
          }}
        />
      </div>
    </div>
  );
}
