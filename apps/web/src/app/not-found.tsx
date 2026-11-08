import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-4 text-center">
      <Compass className="size-14 text-muted-foreground/60" aria-hidden="true" />
      <h1 className="mt-4 text-4xl font-semibold">We can&apos;t find that page</h1>
      <p className="mt-2 text-muted-foreground">
        The link may be old or mistyped. If you were handed a certificate code, you can check it directly.
      </p>
      <div className="mt-6 flex gap-2">
        <Button render={<Link href="/" />} nativeButton={false}>Go home</Button>
        <Button variant="outline" render={<Link href="/verify" />} nativeButton={false}>Verify a certificate</Button>
      </div>
    </div>
  );
}
