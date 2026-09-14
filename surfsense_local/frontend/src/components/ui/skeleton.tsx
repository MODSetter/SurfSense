import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

const SLAB_WIDTHS = ["w-[88%]", "w-[62%]", "w-[76%]", "w-[54%]"]

function SkeletonSlabs() {
  return (
    <div className="flex flex-col gap-1.5">
      {SLAB_WIDTHS.map((width) => (
        <Skeleton key={width} className={cn("h-8 rounded-xl", width)} />
      ))}
    </div>
  )
}

export { Skeleton, SkeletonSlabs }
