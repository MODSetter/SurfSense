import {
  ComposerPrimitive,
  unstable_useMentionAdapter,
  type Unstable_DirectiveFormatter,
  type Unstable_Mention,
} from "@assistant-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"

import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"
import { licenseRefused } from "../license-refused"

import {
  MentionItem,
  MentionItemDescription,
  MentionList,
} from "./mention-list"
import { MENTION_TRIGGER, mentionAt } from "./mention-matcher"
import { pluginListQuery, thirdPartyQuery } from "./mention-queries"

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
 * The plugins a turn may use, as the gateway decides: switched on, connected, allowed, and
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
        !plugin.disconnected &&
        !licenseRefused(plugin) &&
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
  if (plugins.some((plugin) => plugin.enabled && licenseRefused(plugin))) {
    return intl.formatMessage({
      id: "plugins_mentions_license_empty",
      defaultMessage:
        "Your SurfSense license doesn’t unlock these plugins. Check Settings › License.",
    })
  }
  return intl.formatMessage({
    id: "plugins_mentions_all_off_empty",
    defaultMessage: "Your plugins are off. Turn one on from + › Plugins.",
  })
}

/** Typing `@` in an Agentic composer lists the ready plugins to name for the agent, which picks their tools. */
export function PluginMentions() {
  const plugins = useQuery(pluginListQuery)
  const thirdParty = useQuery(thirdPartyQuery)
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
    <MentionList
      render={
        <ComposerPrimitive.Unstable_TriggerPopover
          char={MENTION_TRIGGER}
          adapter={mention.adapter}
          // The rule the startup frame's box uses too.
          matcher={mentionAt}
        />
      }
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
              <MentionItem
                key={item.id}
                render={
                  <ComposerPrimitive.Unstable_TriggerPopoverItem
                    item={item}
                    index={index}
                  />
                }
                className="hover:bg-accent data-[highlighted]:bg-accent"
              >
                <span>{item.label}</span>
                {item.description ? (
                  <MentionItemDescription>
                    {item.description}
                  </MentionItemDescription>
                ) : null}
              </MentionItem>
            ))
          )
        }
      </ComposerPrimitive.Unstable_TriggerPopoverItems>
    </MentionList>
  )
}
