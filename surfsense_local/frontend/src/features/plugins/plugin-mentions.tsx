import {
  ComposerPrimitive,
  unstable_useMentionAdapter,
  type Unstable_DirectiveFormatter,
  type Unstable_Mention,
} from "@assistant-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"

import { intl } from "@/i18n/intl"

import {
  listPlugins,
  pluginsQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
  type Plugin,
} from "./api"
import { opencodeToolName } from "./tool-name"

const MENTION = /@([A-Za-z0-9_-]+)/g

/**
 * A mention reads `@notes_search` in the box and in the sent message: opencode's
 * own name for the tool, which the API looks for in the text. The library's
 * `:tool[label]{name=id}` would show as written, since the composer is a textarea.
 */
const mentionFormatter: Unstable_DirectiveFormatter = {
  serialize: (item) => `@${item.id}`,
  parse(text) {
    const segments: ReturnType<Unstable_DirectiveFormatter["parse"]>[number][] =
      []
    let last = 0
    for (const match of text.matchAll(MENTION)) {
      if (match.index > last) {
        segments.push({ kind: "text", text: text.slice(last, match.index) })
      }
      segments.push({
        kind: "mention",
        type: "tool",
        label: match[1],
        id: match[1],
      })
      last = match.index + match[0].length
    }
    if (last < text.length)
      segments.push({ kind: "text", text: text.slice(last) })
    return segments
  },
}

/** The tools a turn may use, as the gateway decides; one it refuses is ignored if named. */
function readyMentions(
  plugins: Plugin[],
  thirdPartyOn: boolean
): Unstable_Mention[] {
  return plugins
    .filter(
      (plugin) =>
        plugin.enabled && (plugin.source === "first_party" || thirdPartyOn)
    )
    .flatMap((plugin) =>
      plugin.tools
        .filter((tool) => tool.enabled)
        .map((tool) => ({
          id: opencodeToolName(plugin.id, tool.name),
          type: "tool",
          label: intl.formatMessage(
            { id: "plugins_step_label", defaultMessage: "{plugin}: {tool}" },
            { plugin: plugin.name, tool: tool.title ?? tool.name }
          ),
          description: tool.description,
        }))
    )
}

/** Typing `@` in an Agentic composer lists the ready plugin tools to name for the agent. */
export function PluginMentions() {
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
  })
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  const items = useMemo(
    () => readyMentions(plugins.data ?? [], thirdParty.data ?? false),
    [plugins.data, thirdParty.data]
  )
  // Experimental in assistant-ui, with no stable hook as of 0.15.27: on upgrading, use the stable TriggerPopover names and a TriggerAdapter of our own.
  const mention = unstable_useMentionAdapter({
    items,
    includeModelContextTools: false,
    formatter: mentionFormatter,
  })

  return (
    <ComposerPrimitive.Unstable_TriggerPopover
      char="@"
      adapter={mention.adapter}
      aria-label={intl.formatMessage({
        id: "plugins_mentions_aria",
        defaultMessage: "Plugin tools",
      })}
      className="absolute inset-x-1.5 bottom-full z-50 mb-2 max-h-64 overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-md"
    >
      <ComposerPrimitive.Unstable_TriggerPopover.Directive
        formatter={mention.directive.formatter}
      />
      <ComposerPrimitive.Unstable_TriggerPopoverItems>
        {(found) =>
          found.length === 0 ? (
            <p className="px-2 py-1.5 text-sm text-muted-foreground">
              {intl.formatMessage({
                id: "plugins_mentions_empty",
                defaultMessage: "No plugin tools match",
              })}
            </p>
          ) : (
            found.map((item, index) => (
              <ComposerPrimitive.Unstable_TriggerPopoverItem
                key={item.id}
                item={item}
                index={index}
                className="flex w-full flex-col items-start gap-0.5 rounded-lg px-2 py-1.5 text-left text-sm outline-none hover:bg-accent data-[highlighted]:bg-accent"
              >
                <span>{item.label}</span>
                {item.description ? (
                  <span className="line-clamp-1 text-xs text-muted-foreground">
                    {item.description}
                  </span>
                ) : null}
              </ComposerPrimitive.Unstable_TriggerPopoverItem>
            ))
          )
        }
      </ComposerPrimitive.Unstable_TriggerPopoverItems>
    </ComposerPrimitive.Unstable_TriggerPopover>
  )
}
