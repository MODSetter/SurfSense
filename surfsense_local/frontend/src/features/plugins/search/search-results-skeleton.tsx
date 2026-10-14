import { Skeleton } from "@/components/ui/skeleton"

/** The two sections' shape, held while the query settles, so results replace it without a jump. */
export function SearchResultsSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-3">
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="mt-5 h-4 w-20" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  )
}
