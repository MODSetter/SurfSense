import { useEffect, useId, useRef, type SubmitEvent } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field"
import { ExternalLinkIcon } from "@/components/ui/icons"
import { Textarea } from "@/components/ui/textarea"
import { systemInfo } from "@/features/about/system-info"
import { useAppDetails } from "@/features/about/use-app-details"
import { intl } from "@/i18n/intl"

import {
  openIssueReport,
  updateIssueReport,
  useIssueReport,
} from "./issue-report-state"
import { prefilledIssue } from "./prefilled-issue"
import { SessionLogView } from "./session-log-view"
import { sessionLogBridge, useSessionLog } from "./use-session-log"

// An app dialog (`AppDialogs`), so it opens over whatever dialog is open.
export function IssueReportDialog() {
  const descriptionId = useId()
  const includeLogId = useId()
  const descriptionRef = useRef<HTMLTextAreaElement>(null)
  const { open, context, description, includeLog, copyFailed } =
    useIssueReport()
  const setOpen = (open: boolean) => updateIssueReport({ open })
  const hasLog = sessionLogBridge() !== undefined
  const log = useSessionLog(open)
  const details = useAppDetails()

  useEffect(
    () => window.surfsense?.help?.onReportIssue(() => openIssueReport()),
    []
  )

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    if (!description.trim()) return
    const issue = prefilledIssue({
      description,
      error: context.error,
      system: details.data ? systemInfo(details.data) : undefined,
      log: includeLog ? (log.data ?? []) : [],
    })
    if (issue.paste) {
      try {
        await navigator.clipboard.writeText(issue.paste.text)
      } catch {
        // GitHub would open with whatever was copied before, ready to paste into a public issue.
        updateIssueReport({ copyFailed: true })
        return
      }
    }
    if (window.surfsense?.openExternal) {
      void window.surfsense.openExternal(issue.url)
    } else {
      window.open(issue.url, "_blank", "noreferrer")
    }
    if (issue.paste?.into === "logs") {
      toast.success(
        intl.formatMessage({
          id: "feedback_log_copied_toast",
          defaultMessage: "Log copied. Paste it into “Logs” on GitHub.",
        })
      )
    } else if (issue.paste) {
      toast.success(
        intl.formatMessage({
          id: "feedback_report_copied_toast",
          defaultMessage:
            "Report copied. It’s too long for a link, so paste it into “What happened?” on GitHub.",
        })
      )
    }
    updateIssueReport({ description: "", open: false })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] overflow-y-auto select-none sm:max-w-3xl"
        initialFocus={descriptionRef}
      >
        <form
          className="flex min-w-0 flex-col gap-4"
          onSubmit={(event) => void submit(event)}
        >
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage({
                id: "feedback_dialog_title",
                defaultMessage: "Report an issue",
              })}
            </DialogTitle>
            <DialogDescription className="text-pretty">
              {intl.formatMessage({
                id: "feedback_dialog_body",
                defaultMessage:
                  "Describe what went wrong, and GitHub opens with your report filled in for the SurfSense team.",
              })}
            </DialogDescription>
          </DialogHeader>
          {hasLog ? <SessionLogView lines={log.data ?? []} /> : null}
          <Field>
            <FieldLabel htmlFor={descriptionId}>
              {intl.formatMessage({
                id: "feedback_form_description_label",
                defaultMessage: "What went wrong?",
              })}
            </FieldLabel>
            {context.error ? (
              <FieldDescription className="wrap-anywhere select-text">
                {intl.formatMessage(
                  {
                    id: "feedback_form_error_label",
                    defaultMessage: "Error: {error}",
                  },
                  { error: context.error }
                )}
              </FieldDescription>
            ) : null}
            <Textarea
              ref={descriptionRef}
              id={descriptionId}
              className="max-h-40"
              value={description}
              onChange={(event) =>
                updateIssueReport({ description: event.target.value })
              }
              placeholder={intl.formatMessage({
                id: "feedback_form_description_placeholder",
                defaultMessage:
                  "What you were doing, and what happened instead",
              })}
              required
            />
          </Field>
          {hasLog ? (
            <Field orientation="horizontal">
              <Checkbox
                id={includeLogId}
                checked={includeLog}
                onCheckedChange={(checked) =>
                  updateIssueReport({ includeLog: checked === true })
                }
              />
              <FieldContent>
                <FieldLabel htmlFor={includeLogId}>
                  {intl.formatMessage({
                    id: "feedback_form_include_log_label",
                    defaultMessage: "Include the session log",
                  })}
                </FieldLabel>
                <FieldDescription className="text-pretty">
                  {intl.formatMessage({
                    id: "feedback_form_note_body",
                    defaultMessage:
                      "GitHub issues are public. The log is copied for you to paste into “Logs”, so you can remove anything you’d rather not share first.",
                  })}
                </FieldDescription>
              </FieldContent>
            </Field>
          ) : null}
          {copyFailed ? (
            <FieldError>
              {intl.formatMessage({
                id: "feedback_form_copy_error",
                defaultMessage:
                  "Couldn’t copy to your clipboard, so GitHub wasn’t opened. Try again, or leave the log out.",
              })}
            </FieldError>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              {intl.formatMessage({
                id: "feedback_form_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button type="submit" disabled={!description.trim()}>
              {intl.formatMessage({
                id: "feedback_form_submit_button",
                defaultMessage: "Continue on GitHub",
              })}
              <ExternalLinkIcon data-icon="inline-end" />
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
