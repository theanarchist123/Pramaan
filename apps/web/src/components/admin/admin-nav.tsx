"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardCheck, Hammer, Mail } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/admin", label: "Review queue", icon: ClipboardCheck },
  { href: "/admin/builder", label: "Builder", icon: Hammer },
  { href: "/admin/outreach", label: "Outreach", icon: Mail },
];

export function AdminNav() {
  const path = usePathname();
  return (
    <nav aria-label="Admin sections" className="mb-8 flex gap-1 border-b border-border">
      {TABS.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          aria-current={path === href ? "page" : undefined}
          className={cn(
            "-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
            path === href ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon className="size-4" /> {label}
        </Link>
      ))}
    </nav>
  );
}
