"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BadgeCheck, Bot, Code2, LogIn, Moon, Search, Sparkles, Sun, Type, UserRound,
} from "lucide-react";
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { toggleLargeText } from "@/components/site-header";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [code, setCode] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  const go = (href: string) => {
    onOpenChange(false);
    router.push(href);
  };

  const looksLikeCode = /^PRM-[A-Z0-9]{6,}$/i.test(code.trim());

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Command palette">
      <Command>
        <CommandInput placeholder="Go anywhere, or paste a certificate code…" value={code} onValueChange={setCode} />
        <CommandList>
          <CommandEmpty>No matches.</CommandEmpty>
          {looksLikeCode && (
            <CommandGroup heading="Verify">
              <CommandItem onSelect={() => go(`/verify/${code.trim().toUpperCase()}`)}>
                <BadgeCheck /> Verify certificate {code.trim().toUpperCase()}
              </CommandItem>
            </CommandGroup>
          )}
          <CommandGroup heading="Go to">
            <CommandItem onSelect={() => go("/onboard")}>
              <Sparkles /> Create my verified profile
            </CommandItem>
            <CommandItem onSelect={() => go("/verify")}>
              <BadgeCheck /> Verify a certificate
            </CommandItem>
            <CommandItem onSelect={() => go("/mission-control")}>
              <Bot /> Mission Control (live agents)
            </CommandItem>
            <CommandItem onSelect={() => go("/directory")}>
              <Search /> Search the registry
            </CommandItem>
            <CommandItem onSelect={() => go("/developers")}>
              <Code2 /> Developers & API
            </CommandItem>
            <CommandItem onSelect={() => go("/auth?mode=login")}>
              <LogIn /> Sign in
            </CommandItem>
            <CommandItem onSelect={() => go("/me")}>
              <UserRound /> My profiles
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Preferences">
            <CommandItem
              onSelect={() => {
                setTheme(resolvedTheme === "dark" ? "light" : "dark");
                onOpenChange(false);
              }}
            >
              {resolvedTheme === "dark" ? <Sun /> : <Moon />} Toggle dark mode
            </CommandItem>
            <CommandItem
              onSelect={() => {
                toggleLargeText();
                onOpenChange(false);
              }}
            >
              <Type /> Toggle large text
              <CommandShortcut>A+</CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
