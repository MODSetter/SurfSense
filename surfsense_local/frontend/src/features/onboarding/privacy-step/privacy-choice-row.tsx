import { useId, type ReactNode } from "react"

import { Button } from "@/components/ui/button"

/**
 * One question with two equal buttons and nothing chosen until the user picks.
 * A policy that holds it off shows why instead of the buttons.
 */
export function PrivacyChoiceRow({
  title,
  body,
  whatsSent,
  value,
  locked,
  yesLabel,
  noLabel,
  onChange,
}: {
  title: string
  body: string
  whatsSent: ReactNode
  value: boolean | null
  locked: string | null
  yesLabel: string
  noLabel: string
  onChange: (value: boolean) => void
}) {
  const titleId = useId()
  const option = (choice: boolean, label: string) => (
    <Button
      type="button"
      variant="outline"
      aria-pressed={value === choice}
      className="min-w-20 aria-pressed:border-primary aria-pressed:bg-primary/10 aria-pressed:text-foreground"
      onClick={() => onChange(choice)}
    >
      {label}
    </Button>
  )
  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded-xl border p-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <h2 id={titleId} className="text-sm font-medium">
          {title}
        </h2>
        <p className="text-sm text-pretty text-muted-foreground">{body}</p>
        {locked ? (
          <p className="text-sm text-muted-foreground">{locked}</p>
        ) : null}
        {whatsSent}
      </div>
      {locked ? null : (
        <div
          role="group"
          aria-labelledby={titleId}
          className="grid shrink-0 grid-cols-2 gap-2"
        >
          {option(true, yesLabel)}
          {option(false, noLabel)}
        </div>
      )}
    </section>
  )
}
