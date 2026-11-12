"use client";

import { useState } from "react";
import { BadgeCheck, FileJson, ShieldAlert } from "lucide-react";
import { checkCertificateFile, type OfflineOutcome } from "@/lib/offline-verify";
import { cn } from "@/lib/utils";

/** Drop a certificate .json to check it on this device. The file's content is never uploaded. */
export function FileDrop() {
  const [over, setOver] = useState(false);
  const [out, setOut] = useState<OfflineOutcome | null>(null);
  const [name, setName] = useState("");

  async function take(file: File | undefined) {
    if (!file) return;
    setName(file.name);
    if (file.size > 2_000_000) {
      setOut({ kind: "malformed", reason: "That file is too large to be a certificate." });
      return;
    }
    setOut(await checkCertificateFile(await file.text()));
  }

  return (
    <div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          void take(e.dataTransfer.files[0]);
        }}
        className={cn("flex cursor-pointer flex-col items-center gap-1 rounded-2xl border border-dashed p-5 text-center text-sm transition-colors", over ? "border-primary bg-accent" : "border-border")}
      >
        <FileJson className="size-6 text-muted-foreground" />
        <span>Drop a certificate file (.json) to check it on this device</span>
        <input type="file" accept="application/json,.json" className="sr-only" onChange={(e) => void take(e.target.files?.[0])} />
      </label>
      <div aria-live="polite" className="mt-3">
        {out && (
          <div className={cn("flex gap-2 rounded-xl p-3 text-sm", out.kind === "valid" ? "bg-verified-soft" : "bg-pending-soft")}>
            {out.kind === "valid" ? <BadgeCheck className="mt-0.5 size-5 shrink-0 text-verified" /> : <ShieldAlert className="mt-0.5 size-5 shrink-0" />}
            <div>
              {out.kind === "valid" ? (
                <>
                  <p className="font-medium">
                    Authentic: {out.subject} ({out.certId})
                  </p>
                  <p className="text-muted-foreground">
                    Checked on your device against the registry&apos;s published key. This cannot show whether the registry has since revoked it: look the code up online for that.
                  </p>
                </>
              ) : (
                <p>
                  <span className="font-medium">{name || "File"}:</span> {out.reason}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
