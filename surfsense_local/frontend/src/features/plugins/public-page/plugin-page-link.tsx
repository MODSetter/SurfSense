import type { MouseEvent } from "react"

import { ExternalLinkIcon } from "@/components/ui/icons"

/**
 * A listed plugin's homepage or privacy policy, opened on a click with no link popup:
 * the desktop app is told the plugin and the page, and opens the address the reviewed
 * registry lists for it, never one the page passes.
 */
export function PluginPageLink({
  pluginId,
  page,
  url,
}: {
  pluginId: string
  page: "homepage" | "privacy_policy"
  url: string
}) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (!window.surfsense?.openPluginPage) return
    event.preventDefault()
    void window.surfsense.openPluginPage(pluginId, page)
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      onClick={onClick}
      className="inline-flex max-w-full items-center gap-1.5 underline-offset-3 hover:underline"
    >
      <span className="min-w-0 break-all">{url}</span>
      <ExternalLinkIcon aria-hidden className="size-3.5 shrink-0" />
    </a>
  )
}
