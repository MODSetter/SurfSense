import type { ComponentType, MouseEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AudioWaveformIcon,
  Chat01Icon,
  ComputerEthernetIcon,
  Image01Icon,
  InformationCircleIcon,
  LicenseIcon,
  Settings2Icon,
} from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { NetworkSettings } from "@/features/egress/network-settings"
import { LicenseSettings } from "@/features/license/license-settings"
import type { ImportAccepted } from "@/features/migration/api"
import { ImportBundleButton } from "@/features/migration/import-bundle"
import type { ModelSelection } from "@/features/models/selection/api"
import { UpdateSettings } from "@/features/updates/update-settings"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { AppearanceToggle } from "./appearance-toggle"
import { LanguageSelect } from "./language-select"
import { AudioModelsSettings } from "./models/audio-models-settings"
import { ChatModelsSettings } from "./models/chat-models-settings"
import { ImageModelsSettings } from "./models/image-models-settings"
import { SettingsSection } from "./settings-section"

type SettingsNavItem = {
  id: SettingsSectionId
  icon: ComponentType<{ className?: string; strokeWidth?: number }>
}

export type SettingsSectionId =
  | "general"
  | "chat-models"
  | "image-models"
  | "audio-models"
  | "network"
  | "license"

const CLOUD_EXPORT_URL = "https://surfsense.com/sunset"

function openCloudExport(event: MouseEvent<HTMLAnchorElement>) {
  if (!window.surfsense?.openExternal) return
  event.preventDefault()
  void window.surfsense.openExternal(CLOUD_EXPORT_URL)
}

function GeneralSettings({
  onImported,
}: {
  onImported: (accepted: ImportAccepted) => Promise<void> | void
}) {
  return (
    <SettingsSection
      title={intl.formatMessage({ id: "settings_general_title" })}
      description={intl.formatMessage({ id: "settings_general_body" })}
    >
      <div className="flex items-center justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">
            {intl.formatMessage({ id: "settings_general_appearance_title" })}
          </h3>
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({ id: "settings_general_appearance_body" })}
          </p>
        </div>
        <AppearanceToggle />
      </div>
      <div className="mt-8 flex items-center justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 id="settings-general-language" className="text-sm font-medium">
            {intl.formatMessage({ id: "settings_general_language_title" })}
          </h3>
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({ id: "settings_general_language_body" })}
          </p>
        </div>
        <LanguageSelect
          aria-labelledby="settings-general-language"
          className="w-40"
        />
      </div>
      <div className="mt-8 flex items-center justify-between gap-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1">
            <h3 className="text-sm font-medium text-balance">
              {intl.formatMessage({
                id: "settings_general_cloud_import_title",
              })}
            </h3>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="relative inline-flex size-5 items-center justify-center rounded-sm text-muted-foreground transition-colors duration-150 before:absolute before:inset-[-10px] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                  aria-label={intl.formatMessage({
                    id: "settings_general_cloud_import_info_aria",
                  })}
                >
                  <InformationCircleIcon
                    className="size-3.5"
                    strokeWidth={1.5}
                  />
                </button>
              </TooltipTrigger>
              <TooltipContent
                side="top"
                collisionPadding={12}
                className="max-w-64 leading-5 font-normal"
              >
                {intl.formatMessage({
                  id: "settings_general_cloud_import_tooltip",
                })}
              </TooltipContent>
            </Tooltip>
          </div>
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({ id: "settings_general_cloud_import_body" })}
          </p>
          <a
            href={CLOUD_EXPORT_URL}
            target="_blank"
            rel="noreferrer"
            onClick={openCloudExport}
            className="w-fit text-sm text-muted-foreground underline underline-offset-3 hover:text-foreground"
          >
            {intl.formatMessage({ id: "settings_general_cloud_import_link" })}
          </a>
        </div>
        <ImportBundleButton onImported={onImported} />
      </div>
      <UpdateSettings />
    </SettingsSection>
  )
}

// Add future settings pages here; the dialog navigation is generated from this list.
const SETTINGS_SECTIONS = [
  { id: "general", icon: Settings2Icon },
  { id: "chat-models", icon: Chat01Icon },
  { id: "image-models", icon: Image01Icon },
  { id: "audio-models", icon: AudioWaveformIcon },
  { id: "network", icon: ComputerEthernetIcon },
  { id: "license", icon: LicenseIcon },
] satisfies SettingsNavItem[]

const SECTION_LABELS: Record<SettingsSectionId, () => string> = {
  general: () => intl.formatMessage({ id: "settings_nav_general_label" }),
  "chat-models": () => intl.formatMessage({ id: "settings_nav_chat_label" }),
  "image-models": () => intl.formatMessage({ id: "settings_nav_image_label" }),
  "audio-models": () => intl.formatMessage({ id: "settings_nav_audio_label" }),
  network: () => intl.formatMessage({ id: "settings_nav_network_label" }),
  license: () => intl.formatMessage({ id: "settings_nav_license_label" }),
}

export function SettingsDialog({
  open,
  section,
  onOpenChange,
  onSectionChange,
  onModelUnavailable = () => undefined,
  onModelSelected,
  onImported = () => undefined,
}: {
  open: boolean
  section: SettingsSectionId
  onOpenChange: (open: boolean) => void
  onSectionChange: (section: SettingsSectionId) => void
  onModelUnavailable?: () => void
  onModelSelected: (selection: ModelSelection) => void
  onImported?: (accepted: ImportAccepted) => Promise<void> | void
}) {
  const activeSection =
    SETTINGS_SECTIONS.find((candidate) => candidate.id === section) ??
    SETTINGS_SECTIONS[0]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[640px] min-h-0 w-[1000px] max-w-none gap-0 overflow-hidden rounded-2xl p-0 shadow-xl select-none sm:max-w-none">
        <DialogHeader className="sr-only">
          <DialogTitle>
            {intl.formatMessage({ id: "settings_dialog_title" })}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({ id: "settings_dialog_body" })}
          </DialogDescription>
        </DialogHeader>

        <div className="grid h-full min-h-0 grid-cols-[184px_minmax(0,1fr)]">
          <aside className="border-r bg-sidebar p-3 text-sidebar-foreground">
            <p className="px-2 pt-5 pb-3 text-xs font-medium text-muted-foreground">
              {intl.formatMessage({ id: "settings_nav_title" })}
            </p>
            <nav
              className="flex flex-col gap-1"
              aria-label={intl.formatMessage({ id: "settings_nav_aria" })}
            >
              {SETTINGS_SECTIONS.map((section) => {
                const Icon = section.icon
                const selected = section.id === activeSection.id
                return (
                  <Button
                    key={section.id}
                    type="button"
                    variant="ghost"
                    className={cn(
                      "h-10 w-full justify-start rounded-lg",
                      selected &&
                        "bg-sidebar-accent text-sidebar-accent-foreground"
                    )}
                    aria-current={selected ? "page" : undefined}
                    onClick={() => onSectionChange(section.id)}
                  >
                    <Icon />
                    {SECTION_LABELS[section.id]()}
                  </Button>
                )
              })}
            </nav>
          </aside>

          <section className="min-h-0 min-w-0 overflow-hidden bg-popover text-popover-foreground">
            {activeSection.id === "general" ? (
              <GeneralSettings onImported={onImported} />
            ) : null}
            {activeSection.id === "chat-models" ? (
              <ChatModelsSettings
                onModelUnavailable={onModelUnavailable}
                onSelected={onModelSelected}
              />
            ) : null}
            {activeSection.id === "image-models" ? (
              <ImageModelsSettings onModelUnavailable={onModelUnavailable} />
            ) : null}
            {activeSection.id === "audio-models" ? (
              <AudioModelsSettings onModelUnavailable={onModelUnavailable} />
            ) : null}
            {activeSection.id === "network" ? <NetworkSettings /> : null}
            {activeSection.id === "license" ? <LicenseSettings /> : null}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
