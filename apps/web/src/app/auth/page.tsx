"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LogoMark } from "@/components/logo";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

function AuthForm() {
  const { login, register } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/onboard";
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
    <div className="mx-auto flex min-h-[calc(100dvh-3.5rem)] max-w-md flex-col justify-center px-4 py-12">
      <LogoMark className="size-12" />
      <h1 className="mt-4 text-3xl font-semibold">{mode === "register" ? "Create your account" : "Welcome back"}</h1>
      <p className="mt-1 text-muted-foreground">
        {mode === "register"
          ? "Takes a few seconds. Then Saathi takes it from there."
          : "Sign in to continue your profile."}
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        {mode === "register" && (
          <div className="space-y-1.5">
            <Label htmlFor="name">Your name</Label>
            <Input id="name" autoComplete="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-10" />
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="h-10" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password" type="password" required minLength={8}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="h-10"
          />
          {mode === "register" && <p className="text-xs text-muted-foreground">At least 8 characters.</p>}
        </div>
        <Button type="submit" disabled={busy} className="h-10 w-full text-base">
          {busy ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
        </Button>
      </form>
      <button
        type="button"
        className="mt-4 text-sm text-muted-foreground underline-offset-4 hover:underline"
        onClick={() => setMode(mode === "register" ? "login" : "register")}
      >
        {mode === "register" ? "Already have an account? Sign in" : "New here? Create an account"}
      </button>
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
