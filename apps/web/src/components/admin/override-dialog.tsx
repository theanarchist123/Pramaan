"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";

/**
 * A reviewer vouching for a claim the automation could not confirm. It records WHO, WHY and WHAT EVIDENCE, and the claim
 * becomes "Confirmed by a reviewer": never "Document-verified", because no matching document backs it.
 */
export function OverrideDialog({
  claimId,
  claimText,
  onClose,
  onDone,
}: {
  claimId: string | null;
  claimText: string;
  onClose: () => void;
  onDone: (claimId: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = reason.trim().length >= 10 && ref.trim().length >= 5;

  async function submit() {
    if (!claimId) return;
    setBusy(true);
    try {
      await api(`/v1/admin/claims/${claimId}/verify`, {
        method: "POST",
        json: { status: "human", reason: reason.trim(), evidence_ref: ref.trim() },
      });
      toast.success("Recorded: this claim now shows as confirmed by a reviewer");
      onDone(claimId);
      setReason("");
      setRef("");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't record the confirmation");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={claimId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm this claim yourself</DialogTitle>
          <DialogDescription>
            “{claimText.slice(0, 140)}” will show publicly as <strong>Confirmed by a reviewer</strong>. Your name, reason and
            evidence are kept in the record. You cannot do this for your own profile.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <label htmlFor="ov-reason" className="mb-1 block text-sm font-medium">Why are you confirming it?</label>
            <Textarea id="ov-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Checked the original letter against the ministry's honours list" />
          </div>
          <div>
            <label htmlFor="ov-ref" className="mb-1 block text-sm font-medium">What is the evidence?</label>
            <Input id="ov-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="A link, or a case reference" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={!valid || busy} onClick={submit}>Record confirmation</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
