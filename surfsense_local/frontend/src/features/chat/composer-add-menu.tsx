import { useRef, type ChangeEvent } from "react"
import { ComposerPrimitive } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  FilePlus2Icon,
  Image01Icon,
  PlugIcon,
  PlusIcon,
} from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { PluginsMenu } from "@/features/plugins/in-thread/plugins-menu"
import type { PluginsStart } from "@/features/plugins/plugins-settings"
import { SOURCE_FILE_ACCEPT } from "@/features/sources/api"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { HINTED_ROW_CLASS, HintedLabel, MenuItemHint } from "./menu-item-hint"
import { ThinkingMenuItem } from "./thinking-menu-item"

/**
 * The composer's "+": images for this message, sources for the workspace, the
 * thinking switch, and in an Agentic chat its plugins. Images and sources stay
 * separate items, so a picked file is never a guess between the two.
 */
export function ComposerAddMenu({
  readsImages,
  agentic = false,
  thinking,
  onUploadSources,
  isUploadingSources,
  onManagePlugins,
  className,
}: {
  readsImages: boolean
  // The agent reads no attached images yet, so an Agentic chat takes none.
  agentic?: boolean
  // Absent with no model chosen: there is nothing to tell.
  thinking?: { canSkip: boolean }
  // Absent, the menu offers no upload.
  onUploadSources?: (files: File[]) => void
  isUploadingSources: boolean
  // Opens Settings › Plugins; absent, an Agentic chat's menu offers no plugins.
  onManagePlugins?: (start?: PluginsStart) => void
  className?: string
}) {
  const sourceInput = useRef<HTMLInputElement>(null)
  const label = intl.formatMessage({
    id: "chat_composer_add_menu_aria",
    defaultMessage: "Add images, sources, and more",
  })
  const attachLabel = intl.formatMessage({
    id: "chat_composer_attach_images_label",
    defaultMessage: "Attach images",
  })
  const uploadLabel = intl.formatMessage({
    id: "chat_composer_upload_sources_label",
    defaultMessage: "Upload sources",
  })
  const takesImages = readsImages && !agentic
  const attachHint = takesImages
    ? intl.formatMessage({
        id: "chat_composer_attach_images_tooltip",
        defaultMessage: "Add images to this message",
      })
    : readsImages
      ? intl.formatMessage({
          id: "chat_composer_attach_images_agentic_tooltip",
          defaultMessage: "Agentic mode doesn’t read images yet",
        })
      : intl.formatMessage({
          id: "chat_composer_attach_images_unavailable_tooltip",
          defaultMessage: "This model can’t read images",
        })
  const uploadHint = isUploadingSources
    ? intl.formatMessage({
        id: "chat_composer_upload_sources_uploading_tooltip",
        defaultMessage: "Uploading…",
      })
    : intl.formatMessage({
        id: "chat_composer_upload_sources_tooltip",
        defaultMessage: "Add files to this workspace’s sources",
      })
  const pluginsLabel = intl.formatMessage({
    id: "chat_composer_plugins_label",
    defaultMessage: "Plugins",
  })
  const pluginsHint = intl.formatMessage({
    id: "chat_composer_plugins_basic_tooltip",
    defaultMessage: "Plugins work in Agentic chats",
  })
  const uploadSelected = (event: ChangeEvent<HTMLInputElement>) => {
    onUploadSources?.(Array.from(event.target.files ?? []))
    event.target.value = ""
  }

  return (
    <>
      {onUploadSources ? (
        // Outside the popup, which unmounts on close before the picker answers.
        <input
          ref={sourceInput}
          type="file"
          multiple
          accept={SOURCE_FILE_ACCEPT}
          hidden
          tabIndex={-1}
          aria-hidden
          onChange={uploadSelected}
        />
      ) : null}
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger
            render={
              <DropdownMenuTrigger
                render={
                  <Button
                    type="button"
                    size="icon-lg"
                    variant="ghost"
                    className={cn("rounded-xl", className)}
                    aria-label={label}
                  >
                    <PlusIcon className="size-5" />
                  </Button>
                }
              />
            }
          />
          <TooltipContent side="top">{label}</TooltipContent>
        </Tooltip>
        {/* Below by default; Base UI flips it above when the bottom has no room. */}
        <DropdownMenuContent side="bottom" align="start" className="w-52">
          <DropdownMenuGroup>
            {takesImages ? (
              <MenuItemHint hint={attachHint}>
                {/* assistant-ui's own picker, which takes the adapter's accepted types. */}
                <ComposerPrimitive.AddAttachment asChild multiple>
                  <DropdownMenuItem>
                    <Image01Icon />
                    <HintedLabel label={attachLabel} hint={attachHint} />
                  </DropdownMenuItem>
                </ComposerPrimitive.AddAttachment>
              </MenuItemHint>
            ) : (
              <MenuItemHint hint={attachHint}>
                <DropdownMenuItem disabled className={HINTED_ROW_CLASS}>
                  <Image01Icon />
                  <HintedLabel label={attachLabel} hint={attachHint} />
                </DropdownMenuItem>
              </MenuItemHint>
            )}
            {onUploadSources ? (
              <MenuItemHint hint={uploadHint}>
                <DropdownMenuItem
                  disabled={isUploadingSources}
                  className={HINTED_ROW_CLASS}
                  onClick={() => sourceInput.current?.click()}
                >
                  <FilePlus2Icon />
                  <HintedLabel label={uploadLabel} hint={uploadHint} />
                </DropdownMenuItem>
              </MenuItemHint>
            ) : null}
            {thinking ? <ThinkingMenuItem canSkip={thinking.canSkip} /> : null}
            {/* Plugins reach Agentic chats only; a Basic chat says so. */}
            {onManagePlugins ? (
              agentic ? (
                <PluginsMenu onOpen={onManagePlugins} />
              ) : (
                <MenuItemHint hint={pluginsHint}>
                  <DropdownMenuItem disabled className={HINTED_ROW_CLASS}>
                    <PlugIcon />
                    <HintedLabel label={pluginsLabel} hint={pluginsHint} />
                  </DropdownMenuItem>
                </MenuItemHint>
              )
            ) : null}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}
