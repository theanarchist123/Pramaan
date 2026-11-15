import Link from "next/link";
import { ArrowRight, Search } from "lucide-react";

export default function NotFound() {
  return (
    <div className="md:-mt-16">
      <section data-nav-tone="on-light" className="relative overflow-hidden bg-[var(--brand)] text-[var(--on-brand)]">
        <span aria-hidden className="pointer-events-none absolute -right-8 -top-10 select-none font-display text-[24rem] font-extrabold leading-none opacity-[0.12]">404</span>
        <div className="relative mx-auto flex min-h-[85dvh] max-w-5xl flex-col justify-center px-4 pb-16 pt-8 md:pt-28">
          <h1 className="text-balance text-5xl leading-[1.02] md:text-8xl">We can&apos;t find that page.</h1>
          <p className="mt-4 max-w-xl text-lg text-[#3B2E00]">The link may be old or mistyped. If someone handed you a certificate code, you can check it directly.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/" className="inline-flex h-12 items-center gap-2 rounded-full bg-[#14152B] px-6 font-semibold text-white">Go home <ArrowRight className="size-5" /></Link>
            <Link href="/directory" className="inline-flex h-12 items-center gap-2 rounded-full border-2 border-[#14152B] px-6 font-semibold"><Search className="size-4" /> Find people</Link>
            <Link href="/verify" className="inline-flex h-12 items-center rounded-full border-2 border-[#14152B] px-6 font-semibold">Check a certificate</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
