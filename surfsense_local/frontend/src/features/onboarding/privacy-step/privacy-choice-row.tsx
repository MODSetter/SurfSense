import { useId, type ComponentType, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { ButtonGroup } from "@/components/ui/button-group"
import { CheckIcon } from "@/components/ui/icons"
import type { ChoiceText } from "@/features/privacy-choices/choice-text"
import { DetailsTooltip } from "@/features/privacy-choices/details-tooltip"

/**
 * One question with two equal buttons and nothing chosen until the user picks.
 * The summary names every host; the full description is the title's tooltip,
 * and the exact request or report opens below. A policy that holds it off
 * shows why instead of the buttons.
 */
export function PrivacyChoiceRow({
  icon: Icon,
  title,
  text,
  whatsSent,
  value,
  locked,
  yesLabel,
  noLabel,
  onChange,
}: {
  icon: ComponentType<{ className?: string }>
  title: string
  /** Left out when SurfSense would do nothing to describe. */
  text?: ChoiceText
  whatsSent?: ReactNode
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
      className="min-w-20 aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground aria-pressed:hover:bg-primary/90 dark:aria-pressed:border-primary dark:aria-pressed:bg-primary dark:aria-pressed:hover:bg-primary/90"
      onClick={() => onChange(choice)}
    >
      {value === choice ? <CheckIcon data-icon="inline-start" /> : null}
      {label}
    </Button>
  )
  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-3 py-5 first:pt-0 last:pb-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6"
    >
      <div className="flex min-w-0 gap-3">
        <Icon
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-muted-foreground"
        />
        <div className="flex min-w-0 flex-col items-start gap-1">
          <div className="flex items-center gap-1.5">
            <h2 id={titleId} className="text-sm font-medium">
              {title}
            </h2>
            {text ? (
              <DetailsTooltip label={text.label} details={text.details} />
            ) : null}
          </div>
          {text ? (
            <p className="text-sm text-pretty text-muted-foreground">
              {text.summary}
            </p>
          ) : null}
          {locked ? (
            <p className="text-sm text-muted-foreground">{locked}</p>
          ) : null}
          {whatsSent}
        </div>
      </div>
      {locked ? null : (
        <ButtonGroup aria-labelledby={titleId} className="shrink-0 self-start">
          {option(true, yesLabel)}
          {option(false, noLabel)}
        </ButtonGroup>
      )}
    </section>
  )
}
