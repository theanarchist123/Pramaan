"use client";

import { useRef, useState } from "react";
import { Camera } from "lucide-react";
import { toast } from "sonner";
import { Avatar } from "@/components/profile/avatar";
import { Button } from "@/components/ui/button";
import { API_URL, ApiError } from "@/lib/api";
import type { Profile } from "@/lib/types";

/** Your own photo. It is shrunk and re-encoded on the server; on an approved profile a new photo goes back to a reviewer before anyone sees it. */
export function PhotoUpload({ profile, onDone }: { profile: Profile; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function upload(file: File) {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/v1/profiles/${profile.id}/photo`, { method: "POST", body: form, credentials: "include" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new ApiError(res.status, typeof body?.detail === "string" ? body.detail : "Couldn't upload the photo");
      }
      toast.success(profile.status === "approved" ? "Photo saved. A reviewer will look at it before it shows." : "Photo saved");
      onDone();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't upload the photo");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-5 flex items-center gap-4 rounded-2xl border border-border p-3.5">
      <Avatar name={profile.full_name} photo={profile.photo_url} className="size-16" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">Your photo</p>
        <p className="text-sm text-muted-foreground">A clear face photo helps people trust the page. JPG, PNG or WebP, up to 6 MB.</p>
      </div>
      <input id="photo-input" ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" aria-label="Choose a photo" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
      <Button variant="outline" disabled={busy} onClick={() => input.current?.click()}><Camera /> {busy ? "Uploading…" : profile.photo_url ? "Change" : "Add photo"}</Button>
    </div>
  );
}
