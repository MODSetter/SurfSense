import { SettingsSection } from "@/features/settings/settings-section"
import { UpdateSettings } from "@/features/updates/update-settings"
import { intl } from "@/i18n/intl"
import surfSenseLogo from "@/surfsense-logo.svg"

import {
  DISCORD_URL,
  DOCS_URL,
  GITHUB_URL,
  LICENSE_URL,
  bugReportUrl,
  releaseNotesUrl,
} from "./about-links"
import { CopyVersionButton } from "./copy-version-button"
import { ExternalLink } from "./external-link"
import { systemInfo } from "./system-info"
import { Troubleshooting } from "./troubleshooting"
import { useAppDetails } from "./use-app-details"

function AppIdentity({ version }: { version?: string }) {
  return (
    <div className="flex items-center gap-3">
      <span
        aria-hidden="true"
        className="size-10 shrink-0 bg-foreground"
        style={{
          maskImage: `url(${surfSenseLogo})`,
          maskPosition: "center",
          maskRepeat: "no-repeat",
          maskSize: "contain",
        }}
      />
      <div className="flex flex-col">
        <span className="font-heading text-lg font-medium">SurfSense</span>
        {version ? (
          <div className="flex items-center gap-1">
            <span className="text-sm text-muted-foreground tabular-nums">
              {intl.formatMessage(
                {
                  id: "about_identity_version_label",
                  defaultMessage: "Version {version}",
                },
                { version }
              )}
            </span>
            <CopyVersionButton version={version} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function AboutSettings() {
  const { data: details } = useAppDetails()

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "about_settings_title",
        defaultMessage: "About",
      })}
      description={intl.formatMessage({
        id: "about_settings_body",
        defaultMessage:
          "See which version you have, get updates, and find help.",
      })}
      scrollable="all"
    >
      <AppIdentity version={details?.version} />
      <UpdateSettings />

      <div className="mt-8 flex flex-col gap-1">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "about_links_title",
            defaultMessage: "Links",
          })}
        </h3>
        <div className="mt-1 flex flex-col gap-2">
          {details ? (
            <ExternalLink href={releaseNotesUrl(details.version)}>
              {intl.formatMessage({
                id: "about_release_notes_link",
                defaultMessage: "Release notes",
              })}
            </ExternalLink>
          ) : null}
          <ExternalLink href={DOCS_URL}>
            {intl.formatMessage({
              id: "about_docs_link",
              defaultMessage: "Documentation",
            })}
          </ExternalLink>
          <ExternalLink href={GITHUB_URL}>
            {intl.formatMessage({
              id: "about_github_link",
              defaultMessage: "Source code on GitHub",
            })}
          </ExternalLink>
          <ExternalLink href={DISCORD_URL}>
            {intl.formatMessage({
              id: "about_discord_link",
              defaultMessage: "Community on Discord",
            })}
          </ExternalLink>
          {details ? (
            <ExternalLink href={bugReportUrl(systemInfo(details))}>
              {intl.formatMessage({
                id: "about_report_issue_link",
                defaultMessage: "Report an issue",
              })}
            </ExternalLink>
          ) : null}
        </div>
      </div>

      <div className="mt-8 flex flex-col gap-1">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "about_license_title",
            defaultMessage: "License",
          })}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "about_license_body",
            defaultMessage:
              "SurfSense is open source under the Apache License 2.0.",
          })}
        </p>
        <ExternalLink href={LICENSE_URL}>
          {intl.formatMessage({
            id: "about_license_link",
            defaultMessage: "Read the license",
          })}
        </ExternalLink>
      </div>

      {details ? <Troubleshooting details={details} /> : null}
    </SettingsSection>
  )
}
