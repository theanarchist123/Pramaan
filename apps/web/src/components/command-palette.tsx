"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BadgeCheck, LogIn, Moon, Search, Sparkles, Sun, Type, UserRound,
} from "lucide-react";
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { toggleLargeText } from "@/lib/large-text";
import { useI18n } from "@/lib/i18n";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { t } = useI18n();
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
    <CommandDialog open={open} onOpenChange={onOpenChange} title={t("pal.title")}>
      <Command>
        <CommandInput placeholder={t("pal.placeholder")} value={code} onValueChange={setCode} />
        <CommandList>
          <CommandEmpty>{t("pal.none")}</CommandEmpty>
          {looksLikeCode && (
            <CommandGroup heading={t("pal.verifyHeading")}>
              <CommandItem onSelect={() => go(`/verify/${code.trim().toUpperCase()}`)}>
                <BadgeCheck /> {t("pal.verifyCode")} {code.trim().toUpperCase()}
              </CommandItem>
            </CommandGroup>
          )}
          <CommandGroup heading={t("pal.goTo")}>
            <CommandItem onSelect={() => go("/onboard")}>
              <Sparkles /> {t("pal.getListed")}
            </CommandItem>
            <CommandItem onSelect={() => go("/verify")}>
              <BadgeCheck /> {t("pal.checkCert")}
            </CommandItem>
            <CommandItem onSelect={() => go("/directory")}>
              <Search /> {t("pal.find")}
            </CommandItem>
            <CommandItem onSelect={() => go("/auth?mode=login")}>
              <LogIn /> {t("pal.signin")}
            </CommandItem>
            <CommandItem onSelect={() => go("/me")}>
              <UserRound /> {t("pal.myPage")}
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading={t("pal.prefs")}>
            <CommandItem
              onSelect={() => {
                setTheme(resolvedTheme === "dark" ? "light" : "dark");
                onOpenChange(false);
              }}
            >
              {resolvedTheme === "dark" ? <Sun /> : <Moon />} {t("pal.dark")}
            </CommandItem>
            <CommandItem
              onSelect={() => {
                toggleLargeText();
                onOpenChange(false);
              }}
            >
              <Type /> {t("pal.large")}
              <CommandShortcut>A+</CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
