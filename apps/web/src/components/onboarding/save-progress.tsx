"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

/** Shown to a guest: the draft is theirs to keep, but it can't be listed or certified until they create an account. */
export function SaveProgress() {
  const { upgrade } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await upgrade(form.email, form.password, form.name);
      toast.success("Account created. Your draft is saved.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't create the account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="save-h" className="pop mb-4 rounded-3xl bg-card p-5">
      <h2 id="save-h" className="text-2xl">Save your progress</h2>
      <p className="mt-1 text-sm text-muted-foreground">You can keep talking as a guest. To get verified, listed and certified, create an account. We keep everything you have said so far.</p>
      <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="sp-name">Your name</Label>
          <Input id="sp-name" autoComplete="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-11 rounded-2xl" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sp-email">Email</Label>
          <Input id="sp-email" type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="h-11 rounded-2xl" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sp-pw">Password</Label>
          <Input id="sp-pw" type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="h-11 rounded-2xl" />
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" size="lg" disabled={busy}>{busy ? "Please wait…" : "Create account"}</Button>
        </div>
      </form>
    </section>
  );
}
