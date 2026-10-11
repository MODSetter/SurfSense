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

// A plugin id: lowercase words joined by hyphens.
const MENTION = /@([a-z0-9-]+)/g

/**
 * A mention reads `@notes` in the box and in the sent message: the plugin's id,
 * which the API looks for in the text. The library's `:plugin[label]{name=id}`
 * would show as written, since the composer is a textarea.
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
        type: "plugin",
        label: match[1],
        id: match[1],
      })
      last = match.index + match[0].length
    }
    if (last < text.length) {
      segments.push({ kind: "text", text: text.slice(last) })
    }
    return segments
  },
}

/**
 * The plugins a turn may use, as the gateway decides: switched on, allowed, and
 * with a tool on. One the API finds not ready is ignored if named.
 */
function readyMentions(
  plugins: Plugin[],
  thirdPartyOn: boolean
): Unstable_Mention[] {
  return plugins
    .filter(
      (plugin) =>
        plugin.enabled &&
        (plugin.source === "first_party" || thirdPartyOn) &&
        plugin.tools.some((tool) => tool.enabled)
    )
    .map((plugin) => ({
      id: plugin.id,
      type: "plugin",
      label: plugin.name,
      description: plugin.hosts[0] ?? plugin.url,
    }))
}

/** Why `@` lists nothing: nothing connected, third-party plugins refused, or all switched off. */
function emptyMessage(plugins: Plugin[], thirdPartyOn: boolean) {
  if (plugins.length === 0) {
    return intl.formatMessage({
      id: "plugins_mentions_none_empty",
      defaultMessage: "No plugins connected. Add one in Settings › Plugins.",
    })
  }
  if (
    !thirdPartyOn &&
    plugins.every((plugin) => plugin.source !== "first_party")
  ) {
    return intl.formatMessage({
      id: "plugins_mentions_third_party_off_empty",
      defaultMessage:
        "Allow third-party plugins in Settings › Plugins to use them here.",
    })
  }
  return intl.formatMessage({
    id: "plugins_mentions_all_off_empty",
    defaultMessage: "Your plugins are switched off in Settings › Plugins.",
  })
}

/** Typing `@` in an Agentic composer lists the ready plugins to name for the agent, which picks their tools. */
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
        defaultMessage: "Plugins",
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
              {items.length === 0
                ? emptyMessage(plugins.data ?? [], thirdParty.data ?? false)
                : intl.formatMessage({
                    id: "plugins_mentions_empty",
                    defaultMessage: "No plugins match",
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
