/**
 * A provider URL with the user's account details put in, e.g. Databricks'
 * `https://${DATABRICKS_HOST}/…` with their workspace host. A field left empty
 * stays empty, so the URL is visibly incomplete rather than guessed.
 */
export function fillTemplate(
  template: string,
  values: Record<string, string>
): string {
  return template.replace(/\$\{([A-Z0-9_]+)\}/g, (_, name: string) =>
    (values[name] ?? "").trim()
  )
}
