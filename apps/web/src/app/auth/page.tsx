"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

function AuthForm() {
  const { login, register } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  // Only a path on this site: a crafted ?next=https://elsewhere must never become a redirect off-site.
  const rawNext = params.get("next") || "";
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") && !rawNext.includes("\\") ? rawNext : "/onboard";
  // "Sign in" links open the sign-in form; "Get started" links open registration.
  const [mode, setMode] = useState<"login" | "register">(params.get("mode") === "login" ? "login" : "register");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "register") await register(form.email, form.password, form.name);
      else await login(form.email, form.password);
      router.push(next);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="-mt-28 grid min-h-dvh md:-mt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside data-nav-tone="on-light" className="relative hidden overflow-hidden bg-[var(--brand)] p-12 pt-10 text-[var(--on-brand)] lg:flex lg:flex-col lg:justify-between">
        <span aria-hidden className="pointer-events-none absolute -bottom-24 -right-10 select-none font-display text-[26rem] font-extrabold leading-none opacity-[0.1]">P</span>
        <div className="relative">
          <Link href="/" aria-label="Pramaan home" className="mb-10 inline-flex"><Logo /></Link>
          <h2 className="max-w-md text-balance text-5xl leading-[1.05] xl:text-6xl">Your achievements, with the proof.</h2>
          <ul className="mt-8 max-w-md space-y-4 text-lg">
            {[
              ["Talk, don't fill forms", "Tell Saathi your story by voice or text."],
              ["Back it with a document", "We check names and issuers for you."],
              ["Share a certificate anyone can check", "A QR code that proves it's real."],
            ].map(([h, d], i) => (
              <li key={h} className="flex gap-4">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[#14152B] font-display text-lg font-extrabold text-[var(--brand)]">{i + 1}</span>
                <span><b className="block">{h}</b><span className="opacity-85">{d}</span></span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm font-medium opacity-80">Free. You decide what becomes public.</p>
      </aside>

      <div className="flex flex-col justify-center px-4 pb-12 pt-10 sm:px-10 lg:pt-12">
        <div className="mx-auto w-full max-w-md">
          <Link href="/" aria-label="Pramaan home" className="inline-flex lg:hidden"><Logo /></Link>
          <div className="mt-4 inline-flex rounded-full border-2 border-foreground p-1 text-sm font-bold" role="tablist" aria-label="Account">
            {(["register", "login"] as const).map((m) => (
              <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)} className={`rounded-full px-4 py-1.5 transition-colors ${mode === m ? "bg-foreground text-background" : ""}`}>
                {m === "register" ? "Create account" : "Sign in"}
              </button>
            ))}
          </div>
          <h1 className="mt-6 text-balance text-4xl md:text-5xl">{mode === "register" ? "Let's get you listed." : "Welcome back."}</h1>
          <p className="mt-2 text-muted-foreground">
            {mode === "register" ? "Takes a few seconds. Then Saathi takes it from there." : "Sign in to continue your profile."}
          </p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="name">Your name</Label>
                <Input id="name" autoComplete="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-12 rounded-2xl text-base" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="h-12 rounded-2xl text-base" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password" type="password" required minLength={8}
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="h-12 rounded-2xl text-base"
              />
              {mode === "register" && <p className="text-xs text-muted-foreground">At least 8 characters.</p>}
            </div>
            <Button type="submit" disabled={busy} size="lg" className="w-full">
              {busy ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense>
      <AuthForm />
    </Suspense>
  );
}
