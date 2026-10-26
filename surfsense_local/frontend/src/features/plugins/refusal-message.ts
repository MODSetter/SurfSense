import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

/** Why adding a server failed, in the app's words; the server's own text otherwise. */
export function refusalMessage(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "plugin_needs_sign_in":
        return intl.formatMessage({
          id: "plugins_error_plugin_needs_sign_in",
          defaultMessage: "This server needs a key. Add one and try again.",
        })
      case "plugin_sign_in_failed":
        return intl.formatMessage({
          id: "plugins_error_plugin_sign_in_failed",
          defaultMessage:
            "Couldn’t start signing in to this server. Try again later.",
        })
      case "plugin_unreachable":
        return intl.formatMessage({
          id: "plugins_error_plugin_unreachable",
          defaultMessage:
            "Couldn’t reach this server. Check the URL and that the server is running.",
        })
      case "plugin_gone":
        return intl.formatMessage({
          id: "plugins_error_plugin_gone",
          defaultMessage:
            "This address is no longer served; its server may have moved it. Check its documentation for a new one.",
        })
      case "plugin_sse_only":
        return intl.formatMessage({
          id: "plugins_error_plugin_sse_only",
          defaultMessage:
            "This server speaks only the older SSE transport, which SurfSense no longer supports. Use its Streamable HTTP address, which often ends in /mcp.",
        })
      case "plugin_not_mcp":
        return intl.formatMessage({
          id: "plugins_error_plugin_not_mcp",
          defaultMessage:
            "This address doesn’t answer as an MCP server. Check the URL.",
        })
      case "plugin_oauth_needs_client":
        return intl.formatMessage({
          id: "plugins_error_plugin_oauth_needs_client",
          defaultMessage:
            "This server’s sign-in accepts only apps registered with it. Register one with the callback address below, then connect.",
        })
      case "plugin_oauth_refused":
        return intl.formatMessage({
          id: "plugins_error_plugin_oauth_refused",
          defaultMessage:
            "This server’s sign-in refused SurfSense. It may accept only apps it approved; you can try your own registered app below.",
        })
      case "plugin_needs_https":
        return intl.formatMessage({
          id: "plugins_error_plugin_needs_https",
          defaultMessage:
            "A server on another computer must use an https:// URL.",
        })
      case "plugin_already_connected":
        return intl.formatMessage(
          {
            id: "plugins_error_plugin_already_connected",
            defaultMessage: "This server is already connected as {name}.",
          },
          { name: String(error.detail.name ?? "") }
        )
      case "plugin_name_taken":
        return intl.formatMessage(
          {
            id: "plugins_error_plugin_name_taken",
            defaultMessage:
              "A plugin named {name} is already connected. Choose another name.",
          },
          { name: String(error.detail.name ?? "") }
        )
      case "egress_disabled":
        return intl.formatMessage({
          id: "plugins_error_egress_disabled",
          defaultMessage:
            "SurfSense isn’t allowed to contact this server. Allow its host to connect it.",
        })
    }
  }
  return intl.formatMessage({
    id: "plugins_add_error",
    defaultMessage: "Couldn’t connect this server.",
  })
}
