import type { Plugin } from "../api"

// The registry's submission form; GitHub fills a question from the query by its id.
const SUBMISSION_FORM = "https://github.com/MODSetter/SurfSense/issues/new"

/** A custom plugin, already tried here, offered to everyone through the registry. */
export function registrySubmissionUrl(plugin: Plugin): string {
  const query = new URLSearchParams({
    template: "plugin-submit.yml",
    title: `[plugin submission] ${plugin.name}`,
    name: plugin.name,
    url: plugin.url,
  })
  return `${SUBMISSION_FORM}?${query}`
}

export function openRegistrySubmission(plugin: Plugin): void {
  const url = registrySubmissionUrl(plugin)
  if (window.surfsense?.openExternal) void window.surfsense.openExternal(url)
  else window.open(url, "_blank", "noopener,noreferrer")
}
