import type { ReactNode } from "react"

import { formatLabel } from "@/features/studio/studio-formats"
import { intl } from "@/i18n/intl"

import type { AgentStep } from "./api"

/** The name a path ends with, so a line shows `Plan [3].md`, not the whole folder. */
function fileName(path: unknown): string | null {
  if (typeof path !== "string" || !path) return null
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path
}

function text(value: unknown): string | null {
  return typeof value === "string" && value ? value : null
}

/** What one step did, in a sentence whose subject is set as code. */
export function stepLabel(step: AgentStep): ReactNode {
  const subject = (value: string) => (
    <code className="rounded-sm bg-muted px-1 py-0.5 font-mono text-xs text-foreground">
      {value}
    </code>
  )
  const input = step.input
  const command = text(input.command)
  const file = fileName(input.filePath ?? input.path)
  const pattern = text(input.pattern)

  switch (step.tool) {
    case "bash":
      if (command) {
        return intl.formatMessage(
          { id: "agent_steps_shell_label", defaultMessage: "Ran {command}" },
          { command: subject(command) }
        )
      }
      break
    case "read":
      if (file) {
        return intl.formatMessage(
          { id: "agent_steps_read_label", defaultMessage: "Read {file}" },
          { file: subject(file) }
        )
      }
      break
    case "write":
      if (file) {
        return intl.formatMessage(
          { id: "agent_steps_write_label", defaultMessage: "Wrote {file}" },
          { file: subject(file) }
        )
      }
      break
    case "edit":
      if (file) {
        return intl.formatMessage(
          { id: "agent_steps_edit_label", defaultMessage: "Edited {file}" },
          { file: subject(file) }
        )
      }
      break
    case "grep":
    case "surfsense_search_sources": {
      // grep is given a pattern; SurfSense's search, the user's own words.
      const terms = pattern ?? text(input.query)
      if (terms) {
        return intl.formatMessage(
          {
            id: "agent_steps_search_label",
            defaultMessage: "Searched the sources for {pattern}",
          },
          { pattern: subject(terms) }
        )
      }
      break
    }
    case "surfsense_create_artifact": {
      const format = text(input.format)
      if (format) {
        return intl.formatMessage(
          {
            id: "agent_steps_studio_label",
            defaultMessage: "Started {format} in Studio",
          },
          { format: formatLabel({ key: format, label: format }) }
        )
      }
      break
    }
    case "glob":
      if (pattern) {
        return intl.formatMessage(
          {
            id: "agent_steps_find_files_label",
            defaultMessage: "Looked for files matching {pattern}",
          },
          { pattern: subject(pattern) }
        )
      }
      break
    case "todowrite":
      return intl.formatMessage({
        id: "agent_steps_plan_label",
        defaultMessage: "Updated its plan",
      })
  }
  return intl.formatMessage(
    { id: "agent_steps_other_label", defaultMessage: "Used {tool}" },
    { tool: subject(step.tool ?? "?") }
  )
}
