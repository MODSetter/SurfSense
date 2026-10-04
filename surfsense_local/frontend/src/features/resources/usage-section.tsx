import { useId, type ReactNode } from "react"

/** A headed part of the Resources page, in the settings pages' heading style. */
export function UsageSection({
  title,
  body,
  aside,
  children,
}: {
  title: string
  body: string
  aside?: ReactNode
  children: ReactNode
}) {
  const titleId = useId()
  return (
    <section aria-labelledby={titleId}>
      <div className="flex items-start justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 id={titleId} className="text-sm font-medium">
            {title}
          </h3>
          <p className="text-sm text-pretty text-muted-foreground">{body}</p>
        </div>
        {aside}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}
