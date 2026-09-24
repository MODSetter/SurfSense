import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

// English mirrors REASONS in modules/license/router.py; the backend's own text stays the fallback.
const licenseErrorText: Record<string, () => string> = {
  not_a_license_file: () =>
    intl.formatMessage({ id: "license_error_not_a_license_file" }),
  unsupported_algorithm: () =>
    intl.formatMessage({ id: "license_error_unsupported_algorithm" }),
  bad_signature: () =>
    intl.formatMessage({ id: "license_error_bad_signature" }),
  clock_untrusted: () =>
    intl.formatMessage({ id: "license_error_clock_untrusted" }),
  file_expired: () => intl.formatMessage({ id: "license_error_file_expired" }),
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
    : intl.formatMessage({ id: "license_unexpected_error" })
}
