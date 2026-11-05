import { cn } from "@/lib/utils"

/** The text box's shape, shared by the startup frame's textarea and the composer's
 *  rich input, so one replaces the other with nothing moving. */
export function composerTextClassName(placement: "center" | "bottom") {
  return cn(
    "max-h-44 resize-none overflow-y-auto bg-transparent px-2 pt-4 pb-2.5 text-sm outline-none placeholder:text-muted-foreground",
    placement === "center" ? "block min-h-12 w-full" : "min-h-10 flex-1"
  )
}
