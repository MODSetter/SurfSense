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

/** The title the source-pages tool's result opens with, for a turn whose
 *  scope names no titles: every source, or more than 200. */
function pagedSourceTitle(step: AgentStep, documentId: number): string | null {
  const first = step.output?.split("\n", 1)[0] ?? ""
  const found = first.match(/^Source (\d+) \("(.*)"\) (?:has|is) /)
  return found && Number(found[1]) === documentId ? found[2] : null
}

/** The source a read of a revised workbook's cells names, from its result;
 *  null when the read was of a rendered document's script. */
function revisedWorkbookTitle(step: AgentStep): string | null {
  const first = step.output?.split("\n", 1)[0] ?? ""
  const found = first.match(
    /^Artifact \d+, version \d+ of the revised copy of "(.*)", is a workbook\./
  )
  return found ? found[1] : null
}

/** A document's title inside a sentence. */
const documentTitle = (chunks: ReactNode[]) => (
  <em className="text-foreground">{chunks}</em>
)

/** What one step did, in a sentence whose subject is set apart: code as
 *  code, a document by its title. `sourceTitle` names a source by its id,
 *  or null when the turn's scope does not hold it. */
export function stepLabel(
  step: AgentStep,
  sourceTitle: (documentId: number) => string | null = () => null
): ReactNode {
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
    case "surfsense_render_document": {
      const made = step.artifact
      if (made) {
        return (made.created ?? made.version === 1)
          ? intl.formatMessage(
              {
                id: "agent_steps_render_created_label",
                defaultMessage: "Created <doc>{title}</doc> v{version, number}",
              },
              { title: made.title, version: made.version, doc: documentTitle }
            )
          : intl.formatMessage(
              {
                id: "agent_steps_render_updated_label",
                defaultMessage:
                  "Updated <doc>{title}</doc> to v{version, number}",
              },
              { title: made.title, version: made.version, doc: documentTitle }
            )
      }
      // Running, or a run whose script failed: the title it was asked for.
      const title = text(input.title)
      if (title) {
        return intl.formatMessage(
          {
            id: "agent_steps_render_label",
            defaultMessage: "Ran the document script for <doc>{title}</doc>",
          },
          { title, doc: documentTitle }
        )
      }
      break
    }
    case "surfsense_save_page": {
      const made = step.artifact
      if (made) {
        return (made.created ?? made.version === 1)
          ? intl.formatMessage(
              {
                id: "agent_steps_save_page_created_label",
                defaultMessage: "Created <doc>{title}</doc> v{version, number}",
              },
              { title: made.title, version: made.version, doc: documentTitle }
            )
          : intl.formatMessage(
              {
                id: "agent_steps_save_page_updated_label",
                defaultMessage:
                  "Updated <doc>{title}</doc> to v{version, number}",
              },
              { title: made.title, version: made.version, doc: documentTitle }
            )
      }
      // Running, refused or failed: the title it was asked for.
      const title = text(input.title)
      if (title) {
        return intl.formatMessage(
          {
            id: "agent_steps_save_page_label",
            defaultMessage: "Saved the web page <doc>{title}</doc>",
          },
          { title, doc: documentTitle }
        )
      }
      break
    }
    case "surfsense_make_image": {
      const made = step.artifact
      if (made) {
        return (made.created ?? made.version === 1)
          ? intl.formatMessage(
              {
                id: "agent_steps_make_image_created_label",
                defaultMessage: "Created <doc>{title}</doc> v{version, number}",
              },
              { title: made.title, version: made.version, doc: documentTitle }
            )
          : intl.formatMessage(
              {
                id: "agent_steps_make_image_updated_label",
                defaultMessage:
                  "Updated <doc>{title}</doc> to v{version, number}",
              },
              { title: made.title, version: made.version, doc: documentTitle }
            )
      }
      // Running, still being drawn, refused or failed: what it was asked for.
      const title = text(input.title)
      if (title) {
        return intl.formatMessage(
          {
            id: "agent_steps_make_image_label",
            defaultMessage: "Asked for the picture <doc>{title}</doc>",
          },
          { title, doc: documentTitle }
        )
      }
      // While its input streams, a new picture has neither yet.
      return input.artifact_id
        ? intl.formatMessage({
            id: "agent_steps_make_image_edit_label",
            defaultMessage: "Asked to change a picture",
          })
        : intl.formatMessage({
            id: "agent_steps_make_image_unnamed_label",
            defaultMessage: "Asked for a picture",
          })
    }
    case "surfsense_convert_document": {
      const made = step.artifact
      return made
        ? intl.formatMessage(
            {
              id: "agent_steps_convert_label",
              defaultMessage: "Converted <doc>{title}</doc> to PDF",
            },
            { title: made.title, doc: documentTitle }
          )
        : intl.formatMessage({
            id: "agent_steps_convert_untitled_label",
            defaultMessage: "Converted a document to PDF",
          })
    }
    case "surfsense_revise_document": {
      const made = step.artifact
      if (made) {
        return intl.formatMessage(
          {
            id: "agent_steps_revise_label",
            defaultMessage: "Revised <doc>{title}</doc> v{version, number}",
          },
          { title: made.title, version: made.version, doc: documentTitle }
        )
      }
      // Running, refused or failed: no version to name yet.
      return intl.formatMessage({
        id: "agent_steps_revise_pending_label",
        defaultMessage: "Edited a copy of a source file",
      })
    }
    case "surfsense_run_job": {
      const made = step.artifact
      // The file as the turn named it, else the copy the run made of it.
      const workbook =
        (typeof input.document_id === "number"
          ? sourceTitle(input.document_id)
          : null) ?? text(made?.title)
      // A Word file is a contract a redline reviews; any other, a workbook.
      if (workbook && /\.docx$/i.test(workbook))
        return made
          ? intl.formatMessage(
              {
                id: "agent_steps_run_job_review_label",
                defaultMessage: "Reviewed <doc>{contract}</doc>",
              },
              { contract: workbook, doc: documentTitle }
            )
          : intl.formatMessage(
              {
                id: "agent_steps_run_job_review_pending_label",
                defaultMessage: "Started reviewing <doc>{contract}</doc>",
              },
              { contract: workbook, doc: documentTitle }
            )
      if (made) {
        return workbook
          ? intl.formatMessage(
              {
                id: "agent_steps_run_job_label",
                defaultMessage: "Filled in <doc>{workbook}</doc>",
              },
              { workbook, doc: documentTitle }
            )
          : intl.formatMessage({
              id: "agent_steps_run_job_untitled_label",
              defaultMessage: "Filled in a workbook",
            })
      }
      // Still answering, refused or failed: no copy to open yet.
      return workbook
        ? intl.formatMessage(
            {
              id: "agent_steps_run_job_pending_label",
              defaultMessage: "Started filling in <doc>{workbook}</doc>",
            },
            { workbook, doc: documentTitle }
          )
        : intl.formatMessage({
            id: "agent_steps_run_job_pending_untitled_label",
            defaultMessage: "Started filling in a workbook",
          })
    }
    case "surfsense_confirm_job_suggestions": {
      const made = step.artifact
      return made
        ? intl.formatMessage(
            {
              id: "agent_steps_confirm_job_label",
              defaultMessage:
                "Confirmed suggested answers in <doc>{title}</doc>",
            },
            { title: made.title, doc: documentTitle }
          )
        : intl.formatMessage({
            id: "agent_steps_confirm_job_pending_label",
            defaultMessage: "Started confirming suggested answers",
          })
    }
    case "surfsense_read_document": {
      const workbook =
        typeof input.document_id === "number"
          ? (sourceTitle(input.document_id) ??
            pagedSourceTitle(step, input.document_id) ??
            "")
          : revisedWorkbookTitle(step)
      if (workbook === null) {
        return intl.formatMessage({
          id: "agent_steps_read_document_label",
          defaultMessage: "Read the script behind a document",
        })
      }
      return workbook
        ? intl.formatMessage(
            {
              id: "agent_steps_read_workbook_label",
              defaultMessage: "Read the cells of <doc>{title}</doc>",
            },
            { title: workbook, doc: documentTitle }
          )
        : intl.formatMessage({
            id: "agent_steps_read_workbook_untitled_label",
            defaultMessage: "Read the cells of a workbook",
          })
    }
    case "surfsense_list_images":
      if (Array.isArray(input.source_ids)) {
        return intl.formatMessage(
          {
            id: "agent_steps_list_images_label",
            defaultMessage:
              "Looked for images in {count, plural, one {# source} other {# sources}}",
          },
          { count: input.source_ids.length }
        )
      }
      break
    case "surfsense_source_pages": {
      const title =
        typeof input.document_id === "number"
          ? (sourceTitle(input.document_id) ??
            pagedSourceTitle(step, input.document_id))
          : null
      return title
        ? intl.formatMessage(
            {
              id: "agent_steps_source_pages_label",
              defaultMessage: "Looked at pages of <doc>{title}</doc>",
            },
            { title, doc: documentTitle }
          )
        : intl.formatMessage({
            id: "agent_steps_source_pages_untitled_label",
            defaultMessage: "Looked at pages of a source",
          })
    }
    case "surfsense_analyze_data": {
      const title = text(input.title)
      return title
        ? intl.formatMessage(
            {
              id: "agent_steps_analyze_data_label",
              defaultMessage: "Ran the analysis <doc>{title}</doc>",
            },
            { title, doc: documentTitle }
          )
        : intl.formatMessage({
            id: "agent_steps_analyze_data_untitled_label",
            defaultMessage: "Analysed data",
          })
    }
    case "surfsense_pdf_pages":
      return intl.formatMessage(
        {
          id: "agent_steps_pdf_pages_label",
          defaultMessage:
            "{operation, select, merge {Merged PDFs} extract {Took pages out of a PDF} split {Split a PDF} rotate {Rotated PDF pages} reorder {Reordered PDF pages} other {Worked on PDF pages}}",
        },
        { operation: text(input.operation) ?? "other" }
      )
    case "surfsense_pdf_stamp":
      return intl.formatMessage(
        {
          id: "agent_steps_pdf_stamp_label",
          defaultMessage:
            "{kind, select, watermark {Added a watermark to a PDF} page_numbers {Numbered a PDF’s pages} header {Added a header to a PDF} footer {Added a footer to a PDF} other {Stamped a PDF}}",
        },
        { kind: text(input.kind) ?? "other" }
      )
    case "surfsense_search_web": {
      const query = text(input.query)
      if (query) {
        return intl.formatMessage(
          {
            id: "agent_steps_search_web_label",
            defaultMessage: "Searched the web for {query}",
          },
          { query: subject(query) }
        )
      }
      break
    }
    case "surfsense_read_web_page": {
      const url = text(input.url)
      if (url) {
        return intl.formatMessage(
          {
            id: "agent_steps_read_web_page_label",
            defaultMessage: "Read the web page {url}",
          },
          { url: subject(url) }
        )
      }
      break
    }
    case "surfsense_read_youtube_transcript": {
      const url = text(input.url)
      if (url) {
        return intl.formatMessage(
          {
            id: "agent_steps_read_youtube_transcript_label",
            defaultMessage: "Read the transcript of {url}",
          },
          { url: subject(url) }
        )
      }
      break
    }
    case "surfsense_pdf_form":
      return intl.formatMessage(
        {
          id: "agent_steps_pdf_form_label",
          defaultMessage:
            "{action, select, list {Read a PDF form’s fields} fill {Filled in a PDF form} other {Worked on a PDF form}}",
        },
        { action: text(input.action) ?? "other" }
      )
    // A plugin's tools held for the agent: asked for by name or by a search, or
    // loaded when it called one of them it did not hold.
    case "surfsense_loaded_tools":
    case "surfsense_open_plugin":
    case "surfsense_find_tools": {
      const plugin = text(step.loaded_plugin)
      if (plugin) {
        return intl.formatMessage(
          {
            id: "agent_steps_loaded_tools_label",
            defaultMessage: "Loaded {plugin}’s tools",
          },
          { plugin }
        )
      }
      const query = text(input.query)
      if (query) {
        return intl.formatMessage(
          {
            id: "agent_steps_find_tools_label",
            defaultMessage: "Looked for tools to {task}",
          },
          { task: query }
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
