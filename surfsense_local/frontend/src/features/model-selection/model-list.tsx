import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Field,
  FieldContent,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { ScrollArea } from "@/components/ui/scroll-area"

import { modelKey, type SelectableModel } from "./api"

const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1)

export function ModelList({
  models,
  draftKey,
  persistedKey,
  onSelect,
  disabled = false,
  searchable = false,
}: {
  models: SelectableModel[]
  draftKey: string | null
  persistedKey: string | null
  onSelect: (key: string) => void
  disabled?: boolean
  searchable?: boolean
}) {
  const [query, setQuery] = useState("")
  const needle = query.trim().toLowerCase()
  const visible = needle
    ? models.filter((model) => model.name.toLowerCase().includes(needle))
    : models

  const radios = (
    <RadioGroup
      value={draftKey ?? ""}
      onValueChange={onSelect}
      disabled={disabled}
      aria-label="Models"
    >
      {visible.map((model, index) => {
        const key = modelKey(model)
        const id = `model-${model.provider}-${index}`
        return (
          <FieldLabel key={key} htmlFor={id}>
            <Field orientation="horizontal">
              <RadioGroupItem id={id} value={key} />
              <FieldContent>
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <FieldTitle className="truncate">{model.name}</FieldTitle>
                  {key === persistedKey ? (
                    <Badge variant="secondary">Current</Badge>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {model.capabilities.map((capability) => (
                    <Badge key={capability} variant="outline">
                      {titleCase(capability)}
                    </Badge>
                  ))}
                </div>
              </FieldContent>
            </Field>
          </FieldLabel>
        )
      })}
    </RadioGroup>
  )

  return (
    <FieldSet>
      <FieldLegend className="sr-only">Models</FieldLegend>
      {searchable ? (
        <Input
          type="search"
          placeholder="Search models..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="mb-2"
          aria-label="Search models"
        />
      ) : null}
      {visible.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {needle ? "No models match your search." : "No models available yet."}
        </p>
      ) : searchable ? (
        <ScrollArea className="h-72">
          <div className="pr-3">{radios}</div>
        </ScrollArea>
      ) : (
        radios
      )}
    </FieldSet>
  )
}
