import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

// The backend's default license server, for a refusal that names no host;
// Settings › Network shows the host on its row.
const LICENSE_SERVER_HOST = "api.surfsense.com"

// English mirrors REASONS and REFRESH_FAILURES in modules/license/router.py; the backend's own text stays the fallback.
const licenseErrorText: Record<string, (error: ApiError) => string> = {
  not_a_license_file: () =>
    intl.formatMessage({
      id: "license_error_not_a_license_file",
      defaultMessage: "This is not a SurfSense license file.",
    }),
  unsupported_algorithm: () =>
    intl.formatMessage({
      id: "license_error_unsupported_algorithm",
      defaultMessage:
        "This license file uses an algorithm this version cannot check.",
    }),
  bad_signature: () =>
    intl.formatMessage({
      id: "license_error_bad_signature",
      defaultMessage:
        "This license file was not issued by SurfSense, or it was altered.",
    }),
  clock_untrusted: () =>
    intl.formatMessage({
      id: "license_error_clock_untrusted",
      defaultMessage:
        "This computer’s clock is behind the time the license was issued.",
    }),
  file_expired: () =>
    intl.formatMessage({
      id: "license_error_file_expired",
      defaultMessage:
        "This license file has expired; request a fresh copy at surfsense.com/license.",
    }),
  license_none: () =>
    intl.formatMessage({
      id: "license_error_license_none",
      defaultMessage: "No license is added, so there is none to renew.",
    }),
  refresh_not_found: () =>
    intl.formatMessage({
      id: "license_error_refresh_not_found",
      defaultMessage:
        "SurfSense’s license server has no license with this key.",
    }),
  refresh_refused: () =>
    intl.formatMessage({
      id: "license_error_refresh_refused",
      defaultMessage:
        "SurfSense’s license server will not renew this license. Contact support.",
    }),
  refresh_rate_limited: () =>
    intl.formatMessage({
      id: "license_error_refresh_rate_limited",
      defaultMessage:
        "This license was checked too often; try again in an hour.",
    }),
  refresh_unavailable: () =>
    intl.formatMessage({
      id: "license_error_refresh_unavailable",
      defaultMessage:
        "SurfSense’s license server could not send a renewed file; try again later.",
    }),
  // Shown when the consent question was cancelled or could not be asked.
  refresh_egress_blocked: (error) =>
    intl.formatMessage(
      {
        id: "license_error_refresh_egress_blocked",
        defaultMessage:
          "Allow SurfSense’s license server, {host}, in Settings › Network, then try again.",
      },
      {
        host:
          typeof error.detail.host === "string"
            ? error.detail.host
            : LICENSE_SERVER_HOST,
      }
    ),
}

export function translatedLicenseError(error: unknown): string {
  if (error instanceof ApiError && error.code !== null) {
    const text = Object.hasOwn(licenseErrorText, error.code)
      ? licenseErrorText[error.code]
      : undefined
    if (text) return text(error)
  }
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "license_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}
