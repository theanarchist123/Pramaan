"use client";

import { useState } from "react";
import { toast } from "sonner";
import { MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Proves the applicant controls the email on the account. Shown until they have; required before verification. */
export function EmailVerify() {
  const { user, refresh } = useAuth();
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  if (!user || user.email_verified || user.role === "admin") return null;

  async function request() {
    setBusy(true);
    try {
      const r = await api<{ dev_code?: string }>("/v1/auth/otp/request", { method: "POST" });
      setSent(true);
      toast.success(r.dev_code ? `Dev mode — your code is ${r.dev_code}` : `We emailed a 6-digit code to ${user?.email}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't send the code");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    try {
      await api("/v1/auth/otp/verify", { method: "POST", json: { code } });
      await refresh();
      toast.success("Email verified");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't verify the code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex gap-3">
        <MailCheck className="size-6 shrink-0 text-primary" />
        <div>
          <p className="font-semibold">Confirm it&apos;s really you</p>
          <p className="text-sm text-muted-foreground">
            Before we check your profile, verify the email address on your account ({user.email}).
          </p>
        </div>
      </div>
      {!sent ? (
        <Button onClick={request} disabled={busy} className="w-full">Email me a code</Button>
      ) : (
        <div className="flex gap-2">
          <Input
            aria-label="6-digit code" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
            placeholder="123456" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="h-10 font-mono tracking-widest"
          />
          <Button onClick={confirm} disabled={busy || code.length !== 6}>Verify</Button>
        </div>
      )}
    </div>
  );
}
