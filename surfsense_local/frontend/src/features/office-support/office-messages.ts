import { intl } from "@/i18n/intl"

/** Why a LibreOffice the user has cannot be used, from detect's refusal codes. */
export function refusalMessage(code: string | null): string {
  switch (code) {
    case "branch_ended":
      return intl.formatMessage({
        id: "office_support_refusal_branch_ended_status",
        defaultMessage:
          "This version no longer receives security fixes. Update LibreOffice to use it here.",
      })
    case "branch_unsupported":
    case "branch_unknown":
      return intl.formatMessage({
        id: "office_support_refusal_branch_unsupported_status",
        defaultMessage:
          "SurfSense does not support this version of LibreOffice. Update it, or download LibreOffice instead.",
      })
    case "shared_extensions":
      return intl.formatMessage({
        id: "office_support_refusal_shared_extensions_status",
        defaultMessage:
          "It has extensions installed for every user, which would run inside SurfSense too.",
      })
    case "smoke_failed":
      return intl.formatMessage({
        id: "office_support_refusal_smoke_failed_status",
        defaultMessage: "It did not convert a test file.",
      })
    default:
      return intl.formatMessage({
        id: "office_support_refusal_missing_status",
        defaultMessage: "LibreOffice is no longer at this location.",
      })
  }
}

/** What went wrong turning Office support on, from the install's error codes. */
export function errorMessage(code: string): string {
  if (code.startsWith("installed_")) {
    return intl.formatMessage(
      {
        id: "office_support_installed_unusable_error",
        defaultMessage:
          "The LibreOffice you chose can no longer be used. {reason}",
      },
      { reason: refusalMessage(code.slice("installed_".length)) }
    )
  }
  switch (code) {
    case "checksum_mismatch":
      return intl.formatMessage({
        id: "office_support_checksum_error",
        defaultMessage:
          "The download did not match the file SurfSense expects, so it was deleted. Try again.",
      })
    case "unpack_failed":
    case "install_failed":
    case "smoke_failed":
      return intl.formatMessage({
        id: "office_support_install_error",
        defaultMessage:
          "LibreOffice downloaded but did not pass its check, so it was not turned on.",
      })
    case "in_use":
      return intl.formatMessage({
        id: "office_support_in_use_error",
        defaultMessage:
          "LibreOffice is working on a file. Try again when it finishes.",
      })
    default:
      return intl.formatMessage({
        id: "office_support_download_error",
        defaultMessage:
          "The download failed. Check your connection and try again.",
      })
  }
}
