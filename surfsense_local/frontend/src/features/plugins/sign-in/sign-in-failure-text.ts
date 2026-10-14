import { intl } from "@/i18n/intl"

// English mirrors SignInFailure in modules/plugins/remote/sign_in/oauth/sign_in_failure.py;
// the API's own sentence stays the fallback.
const signInFailureText: Record<string, () => string> = {
  sign_in_declined: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_declined",
      defaultMessage: "You declined the sign-in.",
    }),
  sign_in_refused: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_refused",
      defaultMessage: "The provider refused the sign-in.",
    }),
  sign_in_timed_out: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_timed_out",
      defaultMessage: "The sign-in wasn’t finished in time. Try again.",
    }),
  sign_in_host_not_allowed: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_host_not_allowed",
      defaultMessage:
        "SurfSense isn’t allowed to contact the sign-in server. Allow its host and try again.",
    }),
  sign_in_server_unreachable: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_server_unreachable",
      defaultMessage: "The sign-in server couldn’t be reached.",
    }),
  sign_in_tools_not_listed: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_tools_not_listed",
      defaultMessage: "Signed in, but the server couldn’t list its tools.",
    }),
  sign_in_plugin_disconnected: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_plugin_disconnected",
      defaultMessage: "This plugin was disconnected while you were signing in.",
    }),
  sign_in_plugin_already_connected: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_plugin_already_connected",
      defaultMessage:
        "This server was connected under another name while you were signing in.",
    }),
  sign_in_not_finished: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_not_finished",
      defaultMessage: "The sign-in couldn’t be finished.",
    }),
  sign_in_failed: () =>
    intl.formatMessage({
      id: "plugins_error_sign_in_failed",
      defaultMessage: "The sign-in failed.",
    }),
}

/**
 * Why a sign-in failed, in the app's words; the API's own sentence for a reason the
 * app has no words for, and null once the API has forgotten the sign-in.
 */
export function signInFailureMessage(failure: {
  code: string | null
  message: string | null
}): string | null {
  if (failure.code !== null && Object.hasOwn(signInFailureText, failure.code)) {
    return signInFailureText[failure.code]()
  }
  return failure.message
}
