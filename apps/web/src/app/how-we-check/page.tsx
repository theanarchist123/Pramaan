import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, FileSearch, Gavel, MessagesSquare, ShieldCheck } from "lucide-react";
import { StatusTag } from "@/components/ui/status-tag";

export const metadata: Metadata = {
  title: "How we check",
  description: "How Pramaan turns what people say into proof, and exactly when a person steps in.",
};

const STAGES = [
  { Icon: MessagesSquare, title: "You say it", body: "You talk to Saathi in your own words. We write down each achievement as a separate claim and keep your exact words as the first piece of evidence." },
  { Icon: FileSearch, title: "We look for proof", body: "We search public sources for each claim and quote the passage that backs it. If we can't quote it word for word, it doesn't count. You can also upload a document, and we match the name and the issuer." },
  { Icon: Gavel, title: "A rule decides, or a person does", body: "Fixed rules, not an AI model, decide whether a profile is approved. Anything unclear goes to a human reviewer, with the reasons." },
  { Icon: ShieldCheck, title: "We sign it", body: "An approved profile gets a certificate signed with a key only the registry holds. Anyone can check it, and a changed letter fails the check." },
];

const HUMAN = [
  "Every first public listing",
  "Every award claim",
  "Common names that have no second identifying detail (like an institution or a city)",
  "Any change to a profile after it was approved, including a new photo",
  "A document whose name or issuer doesn't match cleanly, or that looks edited",
  "Anything the system is less than 95% sure about",
];

export default function HowWeCheck() {
  return (
    <div className="-mt-28 md:-mt-16">
      <section className="bg-[var(--tile3)] text-[var(--tile3i)]">
        <div className="mx-auto max-w-5xl px-4 pb-16 pt-36 md:pt-28">
          <h1 className="text-balance text-5xl leading-[1.02] md:text-7xl">How we check what people tell us.</h1>
          <p className="mt-4 max-w-2xl text-lg">Plain words, no jargon. What a claim has to go through, and when a person decides instead of a machine.</p>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-4 py-14">
        <h2 className="text-3xl md:text-4xl">Four steps</h2>
        <ol className="mt-6 grid gap-4 sm:grid-cols-2">
          {STAGES.map(({ Icon, title, body }, i) => (
            <li key={title} className="rounded-[1.6rem] border border-border bg-card p-5">
              <span className="mb-3 flex size-11 items-center justify-center rounded-2xl font-display text-xl font-extrabold" style={{ background: `var(--tile${i + 1})`, color: `var(--tile${i + 1}i)` }}>
                <Icon aria-hidden className="size-5" />
              </span>
              <h3 className="text-2xl">{title}</h3>
              <p className="mt-1.5 text-muted-foreground">{body}</p>
            </li>
          ))}
        </ol>

        <h2 className="mt-16 text-3xl md:text-4xl">What the tags mean</h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">Every achievement on a profile carries one of these. They come from the registry&apos;s records, never from the person.</p>
        <dl className="mt-6 grid gap-3 sm:grid-cols-3">
          {([
            ["document", "A document was uploaded, and the name and the issuer match the claim."],
            ["web", "A public source says it. We quote the passage. It's real evidence, but not a document."],
            ["self", "The person said it. We haven't found proof yet."],
          ] as const).map(([kind, text]) => (
            <div key={kind} className="rounded-[1.4rem] border border-border bg-card p-4">
              <dt><StatusTag kind={kind} /></dt>
              <dd className="mt-2 text-sm text-muted-foreground">{text}</dd>
            </div>
          ))}
        </dl>

        <section className="pop mt-16 rounded-[2rem] bg-[var(--stamp-tint)] p-6 text-[var(--ink)] md:p-8" aria-labelledby="human-h">
          <h2 id="human-h" className="text-3xl md:text-4xl">When a person decides</h2>
          <p className="mt-2 max-w-2xl">A profile is approved automatically only when it is at least 95% sure and a document from a recognised issuer matches. Otherwise a person decides. A person always decides for:</p>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {HUMAN.map((h) => (
              <li key={h} className="flex gap-2.5"><span aria-hidden className="mt-2 size-2 shrink-0 rounded-full bg-[var(--brand)]" />{h}</li>
            ))}
          </ul>
          <p className="mt-4 text-sm">If anything goes wrong while checking, the profile goes to a person. It is never approved or published because of an error.</p>
        </section>

        <h2 className="mt-16 text-3xl md:text-4xl">What we don&apos;t do</h2>
        <ul className="mt-4 space-y-2 text-muted-foreground">
          <li>We don&apos;t let an AI model make the final decision on anyone.</li>
          <li>We don&apos;t check government ID databases. A document is read and compared, not looked up with the issuer.</li>
          <li>We don&apos;t publish anyone without their consent, and you can ask for your data to be exported or deleted at any time.</li>
        </ul>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link href="/onboard" className="inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 font-semibold text-primary-foreground">Get listed, free <ArrowRight className="size-5" /></Link>
          <Link href="/verify" className="inline-flex h-12 items-center rounded-full border-2 border-foreground px-6 font-semibold">Check a certificate</Link>
        </div>
      </div>
    </div>
  );
}
