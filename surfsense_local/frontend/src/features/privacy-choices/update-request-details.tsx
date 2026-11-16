import { RelativeTime } from "@/components/relative-time"
import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

import { updatesLockedText } from "./locked-text"
import { SentBody } from "./sent-body"

// The only headers a check sends: the user agent Electron main's session sets
// on every request, and contract 05's three (part A), with what each holds.
function headerRows() {
  return [
    {
      name: "User-Agent",
      value: intl.formatMessage({
        id: "privacy_choices_update_user_agent_header_body",
        defaultMessage: "Always SurfSense, with no version",
      }),
    },
    {
      name: "X-SurfSense-Version",
      value: intl.formatMessage({
        id: "privacy_choices_update_version_header_body",
        defaultMessage: "This app’s version, such as 2.2.4",
      }),
    },
    {
      name: "X-SurfSense-Platform",
      value: intl.formatMessage({
        id: "privacy_choices_update_platform_header_body",
        defaultMessage: "The system and processor, such as win32-x64",
      }),
    },
    {
      name: "X-SurfSense-OS",
      value: intl.formatMessage({
        id: "privacy_choices_update_os_header_body",
        defaultMessage: "The system’s version, such as windows-11 or macos-15",
      }),
    },
  ]
}

function requestText(request: {
  url: string
  headers: Record<string, string>
}) {
  const headers = Object.entries(request.headers).map(
    ([name, value]) => `${name}: ${value}`
  )
  return [`GET ${request.url}`, ...headers].join("\n")
}

/** Where an update check goes, and the last one exactly as it was sent. */
export function UpdateRequestDetails({ state }: { state: PrivacyState }) {
  const { host, fallbackHost, lastRequest, lastCheckedAt } = state.updates
  const locked = updatesLockedText(state)
  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-pretty text-muted-foreground">
        {intl.formatMessage(
          {
            id: "privacy_choices_update_request_body",
            defaultMessage:
              "A check asks {host} for the newest release file for this system, at most once a day and whenever you click Check now. It carries your IP address, as every request does, and no cookies and no ID.",
          },
          { host }
        )}
      </p>
      <p className="text-pretty text-muted-foreground">
        {fallbackHost
          ? intl.formatMessage(
              {
                id: "privacy_choices_update_fallback_body",
                defaultMessage:
                  "If {host} fails or answers with something unexpected, SurfSense asks {fallback} for the same file directly, with only the User-Agent header, so updates never depend on {host}.",
              },
              { host, fallback: fallbackHost }
            )
          : intl.formatMessage(
              {
                id: "privacy_choices_update_mirror_body",
                defaultMessage:
                  "{host} is the update server your organization set. SurfSense asks nowhere else.",
              },
              { host }
            )}
      </p>
      {locked ? <p className="text-muted-foreground">{locked}</p> : null}
      <h3 className="mt-1 text-sm font-medium">
        {intl.formatMessage({
          id: "privacy_choices_update_last_request_title",
          defaultMessage: "Last request",
        })}
      </h3>
      {lastRequest ? (
        <>
          <SentBody
            label={intl.formatMessage({
              id: "privacy_choices_update_last_request_aria",
              defaultMessage: "The last update request",
            })}
            text={requestText(lastRequest)}
          />
          {lastCheckedAt ? (
            <p className="text-xs text-muted-foreground">
              {intl.formatMessage(
                {
                  id: "privacy_choices_update_last_checked_label",
                  defaultMessage: "Last checked {time}",
                },
                { time: <RelativeTime date={new Date(lastCheckedAt)} /> }
              )}
            </p>
          ) : null}
        </>
      ) : (
        <>
          <p className="text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "privacy_choices_update_no_request_empty",
              defaultMessage:
                "No check since SurfSense started. A check sends these headers and no others:",
            })}
          </p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {headerRows().map((row) => (
              <div key={row.name} className="contents">
                <dt className="font-mono">{row.name}</dt>
                <dd className="text-muted-foreground">{row.value}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </div>
  )
}
