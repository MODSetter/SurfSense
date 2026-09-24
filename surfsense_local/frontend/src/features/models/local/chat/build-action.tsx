import { DownloadIcon } from "@/components/ui/icons"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import type { LocalBuild } from "./api"
import { installView } from "./install-view"
import type { InstallState } from "./use-chat-install"

/**
 * One build's Download, Use or In use button, the same wherever a build is
 * listed: a curated row, its other builds, or a searched repo. While that build
 * installs, it names the phase instead of reading as unavailable.
 */
export function BuildAction({
  build,
  label,
  installState,
  disabled,
  runtimeAvailable,
  onAction,
}: {
  build: LocalBuild
  label: string
  installState: InstallState
  disabled: boolean
  runtimeAvailable: boolean
  onAction: (build: LocalBuild) => void
}) {
  const isInstalling =
    installState.status === "installing" &&
    installState.catalogId === build.catalog_id
  const installed = build.installed_as !== null
  // Only physics refuses. Reduced speed installs exactly like full speed.
  const cannotInstall = !installed && (!build.can_install || !runtimeAvailable)

  if (build.selected) {
    return (
      <Button type="button" size="sm" variant="outline" disabled>
        {intl.formatMessage({ id: "models_build_action_in_use_button" })}
      </Button>
    )
  }
  return (
    <Button
      type="button"
      size="sm"
      className="whitespace-nowrap"
      disabled={disabled || cannotInstall}
      aria-label={
        installed
          ? intl.formatMessage(
              { id: "models_build_action_use_aria" },
              {
                model: label,
                quantization: build.quantization,
              }
            )
          : intl.formatMessage(
              { id: "models_build_action_download_aria" },
              {
                model: label,
                quantization: build.quantization,
              }
            )
      }
      onClick={() => onAction(build)}
    >
      {/* A disabled button still reading "Download" while its own bar fills
          reads as unavailable rather than busy, so it names the phase. */}
      {isInstalling ? (
        <>
          <span className="animate-spin" data-icon="inline-start">
            <Spinner className="size-3.5" />
          </span>
          {installView(installState.event).short}
        </>
      ) : (
        <>
          {!installed ? <DownloadIcon data-icon="inline-start" /> : null}
          {installed
            ? intl.formatMessage({ id: "models_build_action_use_button" })
            : intl.formatMessage({ id: "models_build_action_download_button" })}
        </>
      )}
    </Button>
  )
}
