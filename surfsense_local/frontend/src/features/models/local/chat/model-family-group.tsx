import { useId, type ReactNode } from "react"

import { intl } from "@/i18n/intl"

export function ModelFamilyGroup({
  family,
  children,
}: {
  family: string
  children: ReactNode
}) {
  const headingId = useId()
  return (
    <section className="flex flex-col gap-1.5" aria-labelledby={headingId}>
      <h3 id={headingId} className="text-xs font-medium text-muted-foreground">
        {family ||
          intl.formatMessage({ id: "models_family_group_other_label" })}
      </h3>
      <ul
        className="divide-y overflow-hidden rounded-xl border bg-card"
        aria-label={
          family
            ? intl.formatMessage({ id: "models_family_group_aria" }, { family })
            : intl.formatMessage({ id: "models_family_group_other_aria" })
        }
      >
        {children}
      </ul>
    </section>
  )
}
