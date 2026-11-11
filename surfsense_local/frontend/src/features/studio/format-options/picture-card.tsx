import type { ChangeEvent, ComponentType } from "react"

import { CheckIcon } from "@/components/ui/icons"
import { cn } from "@/lib/utils"

/** One choice shown by its picture, its label under it, the chosen one ticked.
 *  A radio underneath, so a group of them keeps the keyboard and screen readers. */
export function PictureCard({
  name,
  value,
  label,
  Art,
  checked,
  disabled = false,
  className,
  onChange,
}: {
  name: string
  value: string
  label: string
  Art: ComponentType<{ className?: string }> | undefined
  checked: boolean
  disabled?: boolean
  className?: string
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <label
      className={cn(
        "group relative flex min-w-0 flex-col gap-1.5",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        className
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        className="peer sr-only"
        onChange={onChange}
      />
      <span
        className={cn(
          "relative flex aspect-3/2 items-center justify-center overflow-hidden rounded-lg border transition-colors duration-150 ease-out peer-focus-visible:ring-2 peer-focus-visible:ring-ring motion-reduce:transition-none",
          checked
            ? "border-primary ring-1 ring-primary"
            : "border-border group-hover:border-foreground/30"
        )}
      >
        {Art ? <Art /> : null}
        {checked ? (
          <span className="absolute top-1.5 right-1.5 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <CheckIcon className="size-3" strokeWidth={2.5} />
          </span>
        ) : null}
      </span>
      <span className="truncate text-sm">{label}</span>
    </label>
  )
}
