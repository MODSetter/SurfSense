import { useQuery } from "@tanstack/react-query"

import { RelativeTime } from "@/components/relative-time"
import { Skeleton } from "@/components/ui/skeleton"
import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

import { usageLockedText } from "./locked-text"
import { SentBody } from "./sent-body"
import { privacyBridge } from "./use-privacy-state"

const asJson = (body: unknown) => JSON.stringify(body, null, 2)

/** Built afresh each time it is shown, so it is what would go next. */
function useNextReport() {
  const privacy = privacyBridge()
  return useQuery({
    queryKey: ["usage-report-preview"],
    queryFn: async () => (await privacy?.previewUsageReport()) ?? null,
    enabled: Boolean(privacy),
    staleTime: 0,
    gcTime: 0,
  })
}

/** The next report, built but not sent, and the last one that was. */
export function UsageReportDetails({ state }: { state: PrivacyState }) {
  const next = useNextReport()
  const { host, enabled, lastSent } = state.usageStatistics
  const locked = usageLockedText(state)
  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-pretty text-muted-foreground">
        {intl.formatMessage(
          {
            id: "privacy_choices_usage_report_body",
            defaultMessage:
              "At most one report a day goes to {host}, as the JSON below, with no cookies. Every value is a range or a fixed word. Like every request it carries your IP address: SurfSense records only the country its host derives from it, never the address.",
          },
          { host }
        )}
      </p>
      {locked ? (
        <p className="text-muted-foreground">{locked}</p>
      ) : enabled !== true ? (
        <p className="text-muted-foreground">
          {intl.formatMessage({
            id: "privacy_choices_usage_report_off_body",
            defaultMessage:
              "Usage statistics are off, so nothing is sent. This is what the next report would be if you turned them on.",
          })}
        </p>
      ) : null}
      <h3 className="mt-1 text-sm font-medium">
        {intl.formatMessage({
          id: "privacy_choices_usage_next_report_title",
          defaultMessage: "Next report",
        })}
      </h3>
      {next.isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : next.data ? (
        <SentBody
          label={intl.formatMessage({
            id: "privacy_choices_usage_next_report_aria",
            defaultMessage: "The next usage report",
          })}
          text={asJson(next.data)}
        />
      ) : (
        <p className="text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "privacy_choices_usage_next_report_empty",
            defaultMessage:
              "SurfSense cannot name this system in a report’s terms, so it sends none from this computer.",
          })}
        </p>
      )}
      <h3 className="mt-1 text-sm font-medium">
        {intl.formatMessage({
          id: "privacy_choices_usage_last_sent_title",
          defaultMessage: "Last sent",
        })}
      </h3>
      {lastSent ? (
        <>
          <p className="text-xs text-muted-foreground">
            {intl.formatMessage(
              {
                id: "privacy_choices_usage_last_sent_label",
                defaultMessage: "Sent {time}",
              },
              { time: <RelativeTime date={new Date(lastSent.at)} /> }
            )}
          </p>
          <SentBody
            label={intl.formatMessage({
              id: "privacy_choices_usage_last_sent_aria",
              defaultMessage: "The last usage report sent",
            })}
            text={asJson(lastSent.body)}
          />
        </>
      ) : (
        <p className="text-muted-foreground">
          {intl.formatMessage({
            id: "privacy_choices_usage_never_sent_empty",
            defaultMessage: "Nothing sent yet.",
          })}
        </p>
      )}
    </div>
  )
}
