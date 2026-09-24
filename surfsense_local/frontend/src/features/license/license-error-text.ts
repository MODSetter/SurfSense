import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

// English mirrors REASONS in modules/license/router.py; the backend's own text stays the fallback.
const licenseErrorText: Record<string, () => string> = {
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
        "This license file has expired; download it again from your account.",
    }),
}

export function translatedLicenseError(error: unknown): string {
  if (error instanceof ApiError && error.code !== null) {
    const text = Object.hasOwn(licenseErrorText, error.code)
      ? licenseErrorText[error.code]
      : undefined
    if (text) return text()
  }
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "license_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}
