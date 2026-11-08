import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12" role="status" aria-label="Loading">
      <Skeleton className="h-10 w-1/2 rounded-lg" />
      <Skeleton className="mt-4 h-5 w-2/3 rounded-lg" />
      <Skeleton className="mt-10 h-64 w-full rounded-2xl" />
    </div>
  );
}
