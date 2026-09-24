import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { CircleAlertIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

export function OfflineState({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <CircleAlertIcon />
      <AlertTitle>
        {intl.formatMessage({ id: "onboarding_offline_title" })}
      </AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        <p>{intl.formatMessage({ id: "onboarding_offline_start_body" })}</p>
        <code>uv run main.py</code>
      </AlertDescription>
    </Alert>
  )
}
