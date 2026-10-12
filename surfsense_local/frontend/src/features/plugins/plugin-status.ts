import { intl } from "@/i18n/intl"

import type { Plugin } from "./api"

export type PluginStatus = {
  label: string
  /** `failure` needs the user; `idle` is not in use; `ok` is working. */
  tone: "failure" | "idle" | "ok"
}

/** One short state per plugin: what needs fixing first, then what keeps it unused, then what waits on the user. */
export function pluginStatus(
  plugin: Plugin,
  thirdPartyAllowed: boolean
): PluginStatus {
  const failure = (label: string): PluginStatus => ({ label, tone: "failure" })
  if (plugin.removed_reason) {
    return failure(
      intl.formatMessage({
        id: "plugins_list_removed_status",
        defaultMessage: "No longer listed",
      })
    )
  }
  switch (plugin.check_failure) {
    case "unreachable":
      return failure(
        intl.formatMessage({
          id: "plugins_list_unreachable_status",
          defaultMessage: "Couldn’t connect",
        })
      )
    case "sign_in":
      return failure(
        plugin.auth_type === "oauth"
          ? intl.formatMessage({
              id: "plugins_list_signed_out_status",
              defaultMessage: "Signed out",
            })
          : intl.formatMessage({
              id: "plugins_list_sign_in_status",
              defaultMessage: "Needs a new key",
            })
      )
    case "needs_license":
      return failure(
        intl.formatMessage({
          id: "plugins_list_needs_license_status",
          defaultMessage: "Needs a license",
        })
      )
    case "license_expired":
      return failure(
        intl.formatMessage({
          id: "plugins_list_license_expired_status",
          defaultMessage: "License expired",
        })
      )
    case "license_revoked":
      return failure(
        intl.formatMessage({
          id: "plugins_list_license_revoked_status",
          defaultMessage: "License revoked",
        })
      )
    case "license_invalid":
      return failure(
        intl.formatMessage({
          id: "plugins_list_license_invalid_status",
          defaultMessage: "License not recognized",
        })
      )
    case null:
      break
  }
  if (plugin.source !== "first_party" && !thirdPartyAllowed) {
    return {
      label: intl.formatMessage({
        id: "plugins_list_third_party_off_status",
        defaultMessage: "Third-party plugins are off",
      }),
      tone: "idle",
    }
  }
  if (!plugin.enabled) {
    return {
      label: intl.formatMessage({
        id: "plugins_list_paused_status",
        defaultMessage: "Paused",
      }),
      tone: "idle",
    }
  }
  if (plugin.tools.some((tool) => tool.change)) {
    return {
      label: intl.formatMessage({
        id: "plugins_list_new_tools_status",
        defaultMessage: "New tools",
      }),
      tone: "ok",
    }
  }
  return {
    label: intl.formatMessage({
      id: "plugins_list_on_status",
      defaultMessage: "On",
    }),
    tone: "ok",
  }
}
