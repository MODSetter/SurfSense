"""Why a sign-in failed, as a code the screen has its own words for; its sentence stays the fallback."""

import enum


# sign-in-failure-text.ts mirrors these — keep the two in sync.
class SignInFailure(enum.StrEnum):
    DECLINED = "sign_in_declined"
    REFUSED = "sign_in_refused"
    TIMED_OUT = "sign_in_timed_out"
    HOST_NOT_ALLOWED = "sign_in_host_not_allowed"
    SERVER_UNREACHABLE = "sign_in_server_unreachable"
    TOOLS_NOT_LISTED = "sign_in_tools_not_listed"
    PLUGIN_REMOVED = "sign_in_plugin_removed"
    PLUGIN_ALREADY_CONNECTED = "sign_in_plugin_already_connected"
    NOT_FINISHED = "sign_in_not_finished"
    FAILED = "sign_in_failed"
