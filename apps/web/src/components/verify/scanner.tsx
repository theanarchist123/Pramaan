"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useMotionPreference } from "@/lib/motion-preference";

declare global {
  interface Window {
    BarcodeDetector?: new (o: { formats: string[] }) => { detect: (v: CanvasImageSource) => Promise<{ rawValue: string }[]> };
  }
}

export const extractCode = (text: string): string | null => /PRM-[2-9A-HJKMNP-TV-Z]{10}/i.exec(text)?.[0].toUpperCase() ?? null;

/**
 * Scan the QR on a certificate with the camera (M-20 viewfinder). Uses the browser's BarcodeDetector where it exists; where it
 * does not (Firefox, older Safari) it says so and the typed code still works. The video never leaves the device.
 */
export function Scanner({ onCode }: { onCode: (code: string) => void }) {
  const { reduced } = useMotionPreference();
  const video = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<"idle" | "starting" | "scanning" | "found" | "error">("idle");
  const [msg, setMsg] = useState("");
  const stream = useRef<MediaStream | null>(null);

  const supported = typeof window !== "undefined" && "BarcodeDetector" in window && !!navigator.mediaDevices?.getUserMedia;
  const stop = () => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  };
  useEffect(() => stop, []);

  async function start() {
    setState("starting");
    setMsg("");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      if (video.current) {
        video.current.srcObject = stream.current;
        await video.current.play();
      }
      setState("scanning");
      const det = new window.BarcodeDetector!({ formats: ["qr_code"] });
      const tick = async () => {
        if (!stream.current || !video.current) return;
        try {
          for (const hit of await det.detect(video.current)) {
            const code = extractCode(hit.rawValue);
            if (code) {
              setState("found");
              stop();
              onCode(code);
              return;
            }
          }
        } catch {
          /* a frame that cannot be read is fine */
        }
        setTimeout(tick, 250);
      };
      void tick();
    } catch {
      stop();
      setState("error");
      setMsg("Could not open the camera. Allow camera access, or type the code instead.");
    }
  }

  if (!supported) {
    return <p className="text-sm text-muted-foreground">This browser cannot scan QR codes. Type the code printed under the QR instead.</p>;
  }
  const corners = [
    "left-0 top-0 border-l-2 border-t-2",
    "right-0 top-0 border-r-2 border-t-2",
    "bottom-0 left-0 border-b-2 border-l-2",
    "bottom-0 right-0 border-b-2 border-r-2",
  ];
  return (
    <div>
      {state === "idle" || state === "error" ? (
        <Button type="button" variant="outline" onClick={start}>
          <Camera /> Scan the QR code
        </Button>
      ) : (
        <div className="relative w-full max-w-sm overflow-hidden rounded-2xl border border-border bg-black">
          <video ref={video} muted playsInline className="aspect-square w-full object-cover" aria-label="Camera view" />
          <div aria-hidden className="pointer-events-none absolute inset-6">
            {corners.map((c) => (
              <span key={c} className={`absolute size-7 ${c} ${state === "found" ? "border-verified" : "border-white"} transition-colors`} />
            ))}
            {state === "scanning" && !reduced && <span className="absolute inset-x-0 top-0 h-0.5 animate-[scanline_1.2s_linear_infinite] bg-white/80" />}
          </div>
          <Button
            type="button"
            size="icon"
            variant="secondary"
            className="absolute right-2 top-2"
            aria-label="Stop scanning"
            onClick={() => {
              stop();
              setState("idle");
            }}
          >
            <X />
          </Button>
        </div>
      )}
      {msg && (
        <p className="mt-2 text-sm text-destructive" role="alert">
          {msg}
        </p>
      )}
    </div>
  );
}
