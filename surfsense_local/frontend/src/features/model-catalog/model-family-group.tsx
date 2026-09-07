import { useId, type ReactNode } from "react"

export function ModelFamilyGroup({
  family,
  children,
}: {
  family: string
  children: ReactNode
}) {
  const headingId = useId()
  return (
    <section className="flex flex-col gap-2" aria-labelledby={headingId}>
      <h3 id={headingId} className="text-sm font-medium text-muted-foreground">
        {family || "Other"}
      </h3>
      <ul
        className="divide-y overflow-hidden rounded-xl border bg-card"
        aria-label={`${family || "Other"} models`}
      >
        {children}
      </ul>
    </section>
  )
}
