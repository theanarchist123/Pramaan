"use client";

import { useEffect } from "react";
import { RotateCcw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error); // visible to developers; users get the friendly version below
  }, [error]);
  return (
    <div role="alert" className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-4 text-center">
      <TriangleAlert className="size-14 text-destructive/70" aria-hidden="true" />
      <h1 className="mt-4 text-3xl font-semibold">Something went wrong</h1>
      <p className="mt-2 text-muted-foreground">
        That wasn&apos;t supposed to happen, and nothing you entered has been lost on our side. Please try again.
      </p>
      {error.digest && <p className="mt-2 font-mono text-xs text-muted-foreground">Reference: {error.digest}</p>}
      <Button className="mt-6" onClick={reset}><RotateCcw /> Try again</Button>
    </div>
  );
}
