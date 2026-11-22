import { Skeleton } from "@/components/ui/skeleton"

/** A thread's messages while they load: one question and the start of a reply. */
export function MessagesSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col">
      <div className="flex flex-col items-end px-6 py-3">
        <Skeleton className="h-10 w-[42%] rounded-2xl rounded-br-md" />
      </div>
      <div className="flex flex-col items-start gap-2 px-6 py-4">
        <Skeleton className="h-4 w-[92%]" />
        <Skeleton className="h-4 w-[80%]" />
        <Skeleton className="h-4 w-[58%]" />
      </div>
    </div>
  )
}
