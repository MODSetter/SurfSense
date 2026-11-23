import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  ChevronDownIcon,
  FilePlus2Icon,
  FolderAddIcon,
  XIcon,
} from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import type { LocalBuild, LocalRow } from "../chat/api"
import { useInstall } from "../installs/use-install"
import type { Skipped } from "./api"
import { appName } from "./app-name"
import { FoundModelRow } from "./found-model-row"
import { unusableReason } from "./unusable-text"
import { useElsewhere, useElsewhereSettings } from "./use-elsewhere"
import { type PickKind, usePickModel } from "./use-pick-model"

/**
 * The chat models other apps downloaded on this computer, offered with nothing
 * to download: Use records the file and loads it where it lies. Says which apps
 * it read and that nothing was changed or sent. With `manage` (Settings), also
 * the switch for looking and the folders a person added.
 *
 * Nothing renders where nothing can be read (Docker), and on a computer with no
 * such models, only the offer to pick a file.
 */
export function ElsewhereSection({
  onUse,
  disabled = false,
  manage = false,
}: {
  /** Choose a model already used in place, by its runtime name. */
  onUse: (name: string) => void
  disabled?: boolean
  manage?: boolean
}) {
  const elsewhere = useElsewhere()
  // Use is choosing: a found model is recorded, loaded and selected in one go.
  const { installs, install, cancel } = useInstall({
    select: true,
    modelType: "text_gen",
  })
  const [picked, setPicked] = useState<LocalRow[]>([])
  // Read when a pick returns, not when it started: the dialog may stay open
  // while something else on the page begins.
  const busy = useRef(disabled)
  useEffect(() => {
    busy.current = disabled
  }, [disabled])
  const picker = usePickModel((row) => {
    const build = row.builds[0]
    if (!build) return
    setPicked((rows) => [row, ...rows.filter((r) => r.id !== row.id)])
    // Busy now, the file is only shown; its Use chooses it once the page is free.
    if (busy.current) return
    if (build.installed_as) onUse(build.installed_as)
    else if (build.catalog_id) void install(build.catalog_id)
  })

  if (elsewhere.isPending) {
    return (
      <p
        role="status"
        className="flex items-center gap-2 text-xs text-muted-foreground"
      >
        <Spinner className="size-3.5" />
        {intl.formatMessage({
          id: "models_elsewhere_looking_status",
          defaultMessage: "Looking for models other apps downloaded…",
        })}
      </p>
    )
  }
  // A failed look must not stand between a person and the rest of the page.
  if (elsewhere.isError || !elsewhere.data.available) return null

  const data = elsewhere.data
  const listed = new Set(data.rows.map((row) => row.found_in?.path))
  // A picked file joins the list once it is recorded; until then it is shown here.
  const rows = [
    ...picked.filter((row) => !listed.has(row.found_in?.path)),
    ...data.rows,
  ]
  const use = (build: LocalBuild) => {
    if (!disabled) void install(build.catalog_id)
  }
  const pickButtons = picker.available ? (
    <PickButtons
      picking={picker.picking}
      disabled={disabled}
      onPick={picker.pick}
    />
  ) : null

  if (!rows.length && !manage) {
    return pickButtons ? (
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p className="text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "models_elsewhere_pick_prompt_body",
            defaultMessage: "Already have a GGUF model on this computer?",
          })}
        </p>
        {pickButtons}
      </div>
    ) : null
  }

  return (
    <section
      className="flex flex-col gap-2.5"
      aria-label={intl.formatMessage({
        id: "models_elsewhere_section_aria",
        defaultMessage: "Models other apps downloaded",
      })}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h3 className="text-sm font-medium">
            {intl.formatMessage({
              id: "models_elsewhere_title",
              defaultMessage: "Already on this computer",
            })}
          </h3>
          <p className="max-w-xl text-xs text-pretty text-muted-foreground">
            {disclosure(data.look, data.looked_in)}
          </p>
        </div>
        {pickButtons}
      </div>

      {manage ? <LookSwitch look={data.look} /> : null}
      {manage && data.folders.length ? (
        <AddedFolders folders={data.folders} />
      ) : null}

      {rows.length ? (
        <ScrollFade
          className="overflow-hidden rounded-xl border bg-card"
          viewportClassName="max-h-56"
        >
          <ul
            className="divide-y"
            aria-label={intl.formatMessage({
              id: "models_elsewhere_list_aria",
              defaultMessage: "Models other apps downloaded",
            })}
          >
            {rows.map((row) => (
              <FoundModelRow
                key={row.found_in?.path ?? row.id}
                row={row}
                installs={installs}
                disabled={disabled}
                onInstall={use}
                onUse={onUse}
                onCancel={cancel}
              />
            ))}
          </ul>
        </ScrollFade>
      ) : (
        <p className="rounded-xl border border-dashed p-4 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "models_elsewhere_empty",
            defaultMessage:
              "No chat models from other apps were found. Pick a file or a folder to use one from somewhere else.",
          })}
        </p>
      )}

      {data.skipped.length ? <SkippedModels skipped={data.skipped} /> : null}
    </section>
  )
}

/** Which apps were read, and the promise that matters: in place, unchanged, unsent. */
function disclosure(look: boolean, lookedIn: string[]): string {
  if (!look) {
    return intl.formatMessage({
      id: "models_elsewhere_look_off_body",
      defaultMessage:
        "Looking in other apps’ folders is off. Folders you added are still read. Files are used where they are and never changed.",
    })
  }
  if (!lookedIn.length) {
    return intl.formatMessage({
      id: "models_elsewhere_nothing_looked_in_body",
      defaultMessage:
        "SurfSense looked for Ollama, LM Studio, Jan, GPT4All, llama.cpp and the Hugging Face cache, and found none of them. Files are used where they are and never changed.",
    })
  }
  return intl.formatMessage(
    {
      id: "models_elsewhere_disclosure_body",
      defaultMessage:
        "Found in {apps}. SurfSense uses each file where it is and never changes it, and nothing leaves this computer.",
    },
    {
      apps: intl.formatList(lookedIn.map(appName), { type: "conjunction" }),
    }
  )
}

function PickButtons({
  picking,
  disabled,
  onPick,
}: {
  picking: PickKind | null
  /** The page is choosing or installing a model: a pick waits for it. */
  disabled: boolean
  onPick: (kind: PickKind) => void
}) {
  const off = disabled || picking !== null
  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={off}
        onClick={() => onPick("file")}
      >
        {picking === "file" ? (
          <Spinner data-icon="inline-start" />
        ) : (
          <FilePlus2Icon data-icon="inline-start" />
        )}
        {intl.formatMessage({
          id: "models_elsewhere_pick_file_button",
          defaultMessage: "Choose a file…",
        })}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={off}
        onClick={() => onPick("folder")}
      >
        {picking === "folder" ? (
          <Spinner data-icon="inline-start" />
        ) : (
          <FolderAddIcon data-icon="inline-start" />
        )}
        {intl.formatMessage({
          id: "models_elsewhere_pick_folder_button",
          defaultMessage: "Add a folder…",
        })}
      </Button>
    </div>
  )
}

function LookSwitch({ look }: { look: boolean }) {
  const settings = useElsewhereSettings()
  const label = intl.formatMessage({
    id: "models_elsewhere_look_label",
    defaultMessage: "Look in other apps’ model folders",
  })
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border p-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm">{label}</span>
        <span className="text-xs text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "models_elsewhere_look_body",
            defaultMessage:
              "Ollama, LM Studio, Jan, GPT4All, llama.cpp and the Hugging Face cache. SurfSense reads only their folder listings and each model’s header, on this computer.",
          })}
        </span>
      </div>
      <Switch
        checked={look}
        aria-label={label}
        disabled={settings.look.isPending}
        onCheckedChange={(checked) => settings.look.mutate(checked)}
      />
    </div>
  )
}

function AddedFolders({ folders }: { folders: string[] }) {
  const settings = useElsewhereSettings()
  return (
    <ul
      className="flex flex-col gap-1"
      aria-label={intl.formatMessage({
        id: "models_elsewhere_folders_aria",
        defaultMessage: "Folders you added",
      })}
    >
      {folders.map((folder) => (
        <li
          key={folder}
          className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 py-1 pr-1 pl-3"
        >
          <code className="truncate text-xs select-text" title={folder}>
            {folder}
          </code>
          <Button
            type="button"
            size="icon-xs"
            variant="ghost"
            disabled={settings.removeFolder.isPending}
            aria-label={intl.formatMessage(
              {
                id: "models_elsewhere_remove_folder_aria",
                defaultMessage: "Stop looking in {folder}",
              },
              { folder }
            )}
            onClick={() => settings.removeFolder.mutate(folder)}
          >
            <XIcon />
          </Button>
        </li>
      ))}
    </ul>
  )
}

function SkippedModels({ skipped }: { skipped: Skipped[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex flex-col gap-1.5">
      <Button
        type="button"
        size="xs"
        variant="ghost"
        className="-ml-2 self-start text-muted-foreground"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <ChevronDownIcon
          data-icon="inline-start"
          className={
            open ? "rotate-180 transition-transform" : "transition-transform"
          }
        />
        {intl.formatMessage(
          {
            id: "models_elsewhere_skipped_button",
            defaultMessage:
              "{count, plural, one {# more model SurfSense can’t run} other {# more models SurfSense can’t run}}",
          },
          { count: skipped.length }
        )}
      </Button>
      {open ? (
        <ul className="flex flex-col gap-1 pl-1 text-xs text-muted-foreground">
          {skipped.map((model) => (
            <li key={model.path} title={model.path}>
              {intl.formatMessage(
                {
                  id: "models_elsewhere_skipped_item_body",
                  defaultMessage: "{name} ({app}): {reason}",
                },
                {
                  name: model.name,
                  app: appName(model.app),
                  reason: unusableReason(model.code, model.reason),
                }
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
