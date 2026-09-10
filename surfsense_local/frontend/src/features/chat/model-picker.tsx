import { useState } from "react"
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
} from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import {
  getAvailableGenerationModels,
  modelKey,
  setGenerationSelection,
  type ModelSelection,
} from "@/features/model-selection/api"
import { cn } from "@/lib/utils"

const installedModelsQueryKey = ["installed-generation-models"] as const
export const modelControlButtonClassName =
  "flex shrink-0 cursor-pointer select-none items-center gap-1.5 rounded-lg px-1.5 py-1 text-[11px] font-normal text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:outline-none"

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
      await queryClient.invalidateQueries({ queryKey: ["model-catalog"] })
      onModelSelected(selection)
    },
  })

  const needle = query.trim().toLowerCase()
  const visibleModels = (installed.data ?? []).filter((candidate) =>
    candidate.name.toLowerCase().includes(needle)
  )

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
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(modelControlButtonClassName, className)}
          title="Change model"
          aria-label={`Model ${model.name}. Change model.`}
        >
          <span className="max-w-48 truncate">{model.name}</span>
          <ChevronDownIcon className="size-3" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-72 p-0">
        <div className="relative p-2">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={query}
            placeholder="Search models"
            aria-label="Search models"
            className="rounded-none border-0 bg-popover pl-9 shadow-none focus-visible:border-0 focus-visible:ring-0 dark:bg-popover"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Escape") {
                event.stopPropagation()
              }
            }}
          />
        </div>

        <ScrollShadow className="h-60" viewportClassName="select-none p-1">
          <div data-slot="model-picker-results" className="relative min-h-full">
            <DropdownMenuGroup>
              <DropdownMenuLabel>Installed models</DropdownMenuLabel>
              {installed.isPending ? (
                <DropdownMenuLabel>Loading models…</DropdownMenuLabel>
              ) : installed.isError ? (
                <DropdownMenuLabel>
                  Could not load installed models
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
                        disabled={selectModel.isPending}
                        className={selected ? "pr-8" : "pr-1.5"}
                      >
                        <span className="sidebar-row-title-fade min-w-0 flex-1 overflow-hidden whitespace-nowrap">
                          {candidate.name}
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
                  {needle ? "No matching models" : "No installed models"}
                </DropdownMenuLabel>
              )}
            </DropdownMenuGroup>
          </div>
        </ScrollShadow>

        <DropdownMenuGroup className="p-1">
          <DropdownMenuItem onSelect={onManageModels}>
            <Settings2Icon />
            Manage models
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
