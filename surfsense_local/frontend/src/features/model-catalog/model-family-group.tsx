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
      <h3
        id={headingId}
        className="text-sm font-medium text-muted-foreground"
      >
        {family || "Other"}
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </section>
  )
}
