import { intl } from "@/i18n/intl"

/** A plugin's tools as its list names them, in two columns, as Claude's connectors show them. */
export function ListedTools({ tools }: { tools: string[] | null }) {
  // Only an older cached registry, from before every entry listed its tools, has none.
  if (!tools?.length) {
    return (
      <p className="text-sm text-muted-foreground">
        {intl.formatMessage({
          id: "plugins_page_tools_unlisted_body",
          defaultMessage: "Tools aren’t listed for this plugin.",
        })}
      </p>
    )
  }
  return (
    <ul className="grid grid-cols-2 gap-2">
      {tools.map((tool) => (
        <li key={tool}>
          <span className="inline-block max-w-full truncate rounded-md bg-muted px-2.5 py-1 text-sm text-muted-foreground">
            {tool}
          </span>
        </li>
      ))}
    </ul>
  )
}
