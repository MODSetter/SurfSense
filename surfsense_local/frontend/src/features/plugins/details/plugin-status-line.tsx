import { Button } from "@/components/ui/button"
import { InformationCircleIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Plugin } from "../api"
import { checkTone, TONE_CLASS } from "../yours/status-tone"

function checkLabel(plugin: Plugin) {
  if (plugin.check_failure === "sign_in" && plugin.needs_own_app) {
    return intl.formatMessage({
      id: "plugins_row_needs_own_app_status",
      defaultMessage: "Needs an OAuth app",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.never_signed_in) {
    return intl.formatMessage({
      id: "plugins_row_not_connected_status",
      defaultMessage: "Not connected",
    })
  }
  if (plugin.check_failure === "unreachable") {
    return intl.formatMessage({
      id: "plugins_row_unreachable_status",
      defaultMessage: "Couldn’t connect",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.needs_scopes.length) {
    return intl.formatMessage({
      id: "plugins_row_needs_scopes_status",
      defaultMessage: "Needs more access",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.auth_type === "oauth") {
    return intl.formatMessage({
      id: "plugins_row_needs_sign_in_status",
      defaultMessage: "Needs sign-in",
    })
  }
  if (plugin.check_failure === "sign_in") {
    return intl.formatMessage({
      id: "plugins_row_sign_in_status",
      defaultMessage: "Needs a new key",
    })
  }
  if (plugin.check_failure === "needs_license") {
    return intl.formatMessage({
      id: "plugins_row_needs_license_status",
      defaultMessage: "Needs a license",
    })
  }
  if (plugin.check_failure === "license_expired") {
    return intl.formatMessage({
      id: "plugins_row_license_expired_status",
      defaultMessage: "License expired",
    })
  }
  if (plugin.check_failure === "license_revoked") {
    return intl.formatMessage({
      id: "plugins_row_license_revoked_status",
      defaultMessage: "License revoked",
    })
  }
  if (plugin.check_failure === "license_invalid") {
    return intl.formatMessage({
      id: "plugins_row_license_invalid_status",
      defaultMessage: "License not recognized",
    })
  }
  if (!plugin.enabled) {
    return intl.formatMessage({
      id: "plugins_row_paused_status",
      defaultMessage: "Off",
    })
  }
  return intl.formatMessage({
    id: "plugins_row_connected_status",
    defaultMessage: "Connected",
  })
}

/** What the line says: its state, in its colour, and at most one reason why, behind its info button. */
function statusOf(plugin: Plugin, unused: boolean) {
  if (unused) {
    // First, as in the list: nothing about it can be acted on until the switch is on.
    return {
      label: intl.formatMessage({
        id: "plugins_row_not_used_status",
        defaultMessage: "Not used",
      }),
      tone: "text-muted-foreground",
      reason: thirdPartyOff(),
    }
  }
  if (plugin.disconnected) {
    return {
      label: intl.formatMessage({
        id: "plugins_row_disconnected_status",
        defaultMessage: "Disconnected",
      }),
      tone: "text-muted-foreground",
      reason: null,
    }
  }
  // As in the list: no engine reaches it until it is added again by its Streamable HTTP address.
  if (plugin.transport === "sse") {
    return {
      label: intl.formatMessage({
        id: "plugins_row_sse_status",
        defaultMessage: "SSE not supported",
      }),
      tone: TONE_CLASS.failure,
      reason: intl.formatMessage(
        {
          id: "plugins_row_sse_body",
          defaultMessage:
            "SurfSense no longer supports the older SSE transport. Remove {plugin} and add its Streamable HTTP address, which often ends in /mcp.",
        },
        { plugin: plugin.name }
      ),
    }
  }
  if (plugin.removed_reason) {
    return {
      label: intl.formatMessage({
        id: "plugins_row_removed_status",
        defaultMessage: "No longer listed",
      }),
      tone: TONE_CLASS.warning,
      // The registry's own words.
      reason: plugin.removed_reason,
    }
  }
  return {
    label: checkLabel(plugin),
    tone: plugin.check_failure
      ? TONE_CLASS[checkTone(plugin)]
      : "text-muted-foreground",
    reason: ownAppReason(plugin),
  }
}

function ownAppReason(plugin: Plugin) {
  if (!plugin.needs_own_app || plugin.check_failure !== "sign_in") return null
  return plugin.needs_own_app === "refused"
    ? intl.formatMessage(
        {
          id: "plugins_row_own_app_refused_body",
          defaultMessage:
            "{plugin} refused to register SurfSense; it may accept only apps it approved.",
        },
        { plugin: plugin.name }
      )
    : intl.formatMessage(
        {
          id: "plugins_row_own_app_needs_client_body",
          defaultMessage: "{plugin} accepts only apps registered with it.",
        },
        { plugin: plugin.name }
      )
}

function thirdPartyOff() {
  return intl.formatMessage({
    id: "plugins_row_third_party_off_body",
    defaultMessage: "Not used until third-party plugins are allowed",
  })
}

/** A plugin's state, and why behind an info button beside it: the action that needs the reason,
 * such as Connect's own-app dialog, says it again where it matters. */
export function PluginStatusLine({
  plugin,
  unused,
  checking,
}: {
  plugin: Plugin
  /** A third-party plugin while third-party plugins are off. */
  unused: boolean
  checking: boolean
}) {
  const status = statusOf(plugin, unused)
  return (
    <p className="mt-4 flex items-center gap-1.5 text-xs">
      <span className={cn("font-medium", status.tone)}>{status.label}</span>
      {status.reason ? (
        <Tooltip>
          {/* Named by the reason, so a screen reader hears it without the tooltip. */}
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="bare"
                aria-label={status.reason}
                className="inline-flex text-muted-foreground hover:text-foreground"
              />
            }
          >
            <InformationCircleIcon className="size-3.5" />
          </TooltipTrigger>
          <TooltipContent className="max-w-64">{status.reason}</TooltipContent>
        </Tooltip>
      ) : null}
      {checking ? <Spinner className="size-3 text-muted-foreground" /> : null}
    </p>
  )
}
