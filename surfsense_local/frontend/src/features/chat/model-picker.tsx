import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  ChevronDownIcon,
  DotIcon,
  SearchIcon,
  Settings2Icon,
  XIcon,
} from "@/components/ui/icons"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { getAvailableGenerationModels } from "@/features/models/chat-candidates/api"
import { MODELS_QUERY_KEY } from "@/features/models/models-query"
import {
  modelKey,
  setGenerationSelection,
  type ModelSelection,
} from "@/features/models/selection/api"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

// Under the shared models key, so a change made in settings reaches this list.
const installedModelsQueryKey = [
  ...MODELS_QUERY_KEY,
  "chat-candidates",
] as const
export const modelControlButtonClassName =
  "flex shrink-0 cursor-pointer select-none items-center gap-1.5 rounded-lg px-1.5 py-1 text-[11px] font-normal text-muted-foreground hover:bg-accent hover:text-foreground aria-expanded:bg-accent aria-expanded:text-foreground focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:outline-none"

export function ModelPicker({
  model,
  onModelSelected,
  onManageModels,
  className,
}: {
  model: ModelSelection
  onModelSelected: (selection: ModelSelection) => void
  onManageModels: () => void
  className?: string
}) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState("")
  const searchRef = useRef<HTMLInputElement>(null)
  const installed = useQuery({
    queryKey: installedModelsQueryKey,
    queryFn: async ({ signal }) => {
      return getAvailableGenerationModels(signal)
    },
  })
  const selectModel = useMutation({
    mutationFn: (key: string) => {
      const selected = installed.data?.find(
        (candidate) => modelKey(candidate) === key
      )
      if (!selected) {
        throw new Error("This model is no longer available")
      }
      return setGenerationSelection(selected)
    },
    onSuccess: async (selection) => {
      await queryClient.invalidateQueries({ queryKey: MODELS_QUERY_KEY })
      onModelSelected(selection)
    },
  })

  const needle = query.trim().toLowerCase()
  const visibleModels = (installed.data ?? []).filter((candidate) =>
    (candidate.display_name ?? candidate.name).toLowerCase().includes(needle)
  )
  const selectedCandidate = installed.data?.find(
    (candidate) => modelKey(candidate) === modelKey(model)
  )
  const selectedLabel = selectedCandidate?.display_name ?? model.name

  return (
    <DropdownMenu
      onOpenChange={(open) => {
        if (open) {
          void installed.refetch()
        } else {
          setQuery("")
        }
      }}
    >
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            // Shares the row with the disclaimer, truncating the model name
            // rather than forcing a long translation onto more lines.
            className={cn(
              modelControlButtonClassName,
              "min-w-0 shrink",
              className
            )}
            title={intl.formatMessage({
              id: "chat_model_picker_change_tooltip",
              defaultMessage: "Change model",
            })}
            aria-label={intl.formatMessage(
              {
                id: "chat_model_picker_trigger_aria",
                defaultMessage: "Model {model}. Change model.",
              },
              {
                model: selectedLabel,
              }
            )}
          >
            <span className="max-w-48 truncate">{selectedLabel}</span>
            <ChevronDownIcon className="size-3" />
          </button>
        }
      />

      <DropdownMenuContent align="end" className="w-72 p-0">
        <div className="px-1 py-2">
          {/* The menu's top bar, so it stays borderless. The icon lines up
              with the list's labels below (4px + 6px). */}
          <InputGroup className="border-0 bg-popover dark:bg-popover">
            <InputGroupAddon className="pl-1.5">
              <SearchIcon />
            </InputGroupAddon>
            <InputGroupInput
              ref={searchRef}
              type="search"
              value={query}
              placeholder={intl.formatMessage({
                id: "chat_model_picker_search_placeholder",
                defaultMessage: "Search models",
              })}
              aria-label={intl.formatMessage({
                id: "chat_model_picker_search_aria",
                defaultMessage: "Search models",
              })}
              // The clear button below replaces the browser's own.
              className="[&::-webkit-search-cancel-button]:appearance-none"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Escape") {
                  event.stopPropagation()
                }
              }}
            />
            {query ? (
              <InputGroupAddon align="inline-end">
                <InputGroupButton
                  size="icon-xs"
                  aria-label={intl.formatMessage({
                    id: "chat_model_picker_search_clear_aria",
                    defaultMessage: "Clear search",
                  })}
                  onClick={() => {
                    setQuery("")
                    searchRef.current?.focus()
                  }}
                >
                  <XIcon />
                </InputGroupButton>
              </InputGroupAddon>
            ) : null}
          </InputGroup>
        </div>

        <ScrollFade className="h-60" viewportClassName="select-none p-1">
          <div data-slot="model-picker-results" className="relative min-h-full">
            <DropdownMenuGroup>
              <DropdownMenuLabel>
                {intl.formatMessage({
                  id: "chat_model_picker_installed_title",
                  defaultMessage: "Installed models",
                })}
              </DropdownMenuLabel>
              {installed.isPending ? (
                <DropdownMenuLabel>
                  {intl.formatMessage({
                    id: "chat_model_picker_loading_status",
                    defaultMessage: "Loading models…",
                  })}
                </DropdownMenuLabel>
              ) : installed.isError ? (
                <DropdownMenuLabel>
                  {intl.formatMessage({
                    id: "chat_model_picker_load_error",
                    defaultMessage: "Could not load installed models",
                  })}
                </DropdownMenuLabel>
              ) : visibleModels.length > 0 ? (
                <DropdownMenuRadioGroup
                  value={modelKey(model)}
                  onValueChange={(key) => selectModel.mutate(key)}
                >
                  {visibleModels.map((candidate) => {
                    const key = modelKey(candidate)
                    const selected = key === modelKey(model)
                    return (
                      <DropdownMenuRadioItem
                        key={key}
                        value={key}
                        // Radix closed on pick; Base UI radio items stay open.
                        closeOnClick
                        disabled={selectModel.isPending}
                        className={selected ? "pr-8" : "pr-1.5"}
                      >
                        <span className="sidebar-row-title-fade min-w-0 flex-1 overflow-hidden whitespace-nowrap">
                          {candidate.display_name ?? candidate.name}
                          {candidate.connection_label ? (
                            <span className="ml-1 inline-flex items-center gap-1 align-middle text-muted-foreground">
                              <DotIcon
                                aria-hidden="true"
                                className="size-3 shrink-0"
                              />
                              {candidate.connection_label}
                            </span>
                          ) : null}
                        </span>
                      </DropdownMenuRadioItem>
                    )
                  })}
                </DropdownMenuRadioGroup>
              ) : (
                <DropdownMenuLabel
                  className={
                    needle
                      ? "absolute inset-0 flex items-center justify-center"
                      : undefined
                  }
                >
                  {needle
                    ? intl.formatMessage({
                        id: "chat_model_picker_no_match_empty",
                        defaultMessage: "No matching models",
                      })
                    : intl.formatMessage({
                        id: "chat_model_picker_none_installed_empty",
                        defaultMessage: "No installed models",
                      })}
                </DropdownMenuLabel>
              )}
            </DropdownMenuGroup>
          </div>
        </ScrollFade>

        <DropdownMenuGroup className="p-1">
          <DropdownMenuItem onClick={onManageModels}>
            <Settings2Icon />
            {intl.formatMessage({
              id: "chat_model_picker_manage_label",
              defaultMessage: "Manage models",
            })}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
