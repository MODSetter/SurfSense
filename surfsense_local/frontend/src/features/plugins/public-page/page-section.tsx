import { useId, type ReactNode } from "react"

/** One titled part of a plugin's page: About, Tools or Details. */
export function PageSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  const titleId = useId()
  return (
    <section aria-labelledby={titleId} className="mt-6">
      <h4 id={titleId} className="mb-2 text-sm font-medium">
        {title}
      </h4>
      {children}
    </section>
  )
}
