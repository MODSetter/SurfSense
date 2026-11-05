import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { DotIcon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { studioKeys } from "@/features/studio/query-keys"
import { intl } from "@/i18n/intl"

import { confirmRunSuggestions, type OpenSuggestion } from "../api"
import { jobsErrorText } from "../job-error-text"
import { jobsKeys } from "../query-keys"

/**
 * Confirms every suggested answer a run left open, as the next version of its
 * copy, after the user has seen each one. The Jobs screen and Studio show the
 * same button.
 */
export function ConfirmSuggestionsButton({
  workspaceId,
  rootId,
  suggestions,
  disabled = false,
  size = "default",
}: {
  workspaceId: number
  // The run's own version: confirming always names it.
  rootId: number
  suggestions: readonly OpenSuggestion[]
  disabled?: boolean
  size?: "sm" | "default"
}) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const confirm = useMutation({
    mutationFn: () => confirmRunSuggestions(workspaceId, rootId),
    // Here, not on mutate: the button unmounts once nothing is left open.
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: studioKeys.artifacts(workspaceId),
      })
      void queryClient.invalidateQueries({
        queryKey: jobsKeys.runs(workspaceId),
      })
      toast.success(
        intl.formatMessage({
          id: "jobs_confirm_started_toast",
          defaultMessage: "Writing the confirmed answers into a new version",
        })
      )
    },
  })
  const count = suggestions.length

  return (
    <>
      <Button
        type="button"
        size={size}
        disabled={disabled}
        onClick={() => {
          confirm.reset()
          setOpen(true)
        }}
      >
        {intl.formatMessage(
          {
            id: "jobs_confirm_button",
            defaultMessage:
              "Confirm {count, plural, one {# suggested answer} other {# suggested answers}}",
          },
          { count }
        )}
      </Button>
      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          if (!confirm.isPending) setOpen(next)
        }}
      >
        <AlertDialogContent className="select-none sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {intl.formatMessage(
                {
                  id: "jobs_confirm_dialog_title",
                  defaultMessage:
                    "Confirm {count, plural, one {# suggested answer} other {# suggested answers}}?",
                },
                { count }
              )}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {intl.formatMessage({
                id: "jobs_confirm_dialog_body",
                defaultMessage:
                  "Each one is written into its cell in a new version of this copy, and the exceptions sheet notes that a person confirmed it. Confirm them only once you have checked them.",
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <ScrollFade className="max-h-64" viewportClassName="pr-2">
            <ul
              aria-label={intl.formatMessage({
                id: "jobs_confirm_dialog_list_aria",
                defaultMessage: "Suggested answers",
              })}
              className="flex flex-col gap-3"
            >
              {suggestions.map((suggestion) => (
                <li
                  key={`${suggestion.sheet}!${suggestion.cell}`}
                  className="flex flex-col gap-0.5"
                >
                  <span className="line-clamp-2 text-sm">
                    {suggestion.question}
                  </span>
                  <span className="flex flex-wrap items-center text-xs text-muted-foreground">
                    <span>
                      {intl.formatMessage(
                        {
                          id: "jobs_confirm_suggested_label",
                          defaultMessage: "Suggested: {answer}",
                        },
                        { answer: suggestion.written || suggestion.suggested }
                      )}
                    </span>
                    <DotIcon aria-hidden="true" className="size-3 shrink-0" />
                    <span>
                      {intl.formatMessage(
                        {
                          id: "jobs_confirm_cell_label",
                          defaultMessage: "{sheet}, cell {cell}",
                        },
                        { sheet: suggestion.sheet, cell: suggestion.cell }
                      )}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </ScrollFade>
          {confirm.error ? (
            <p role="alert" className="text-sm text-pretty text-destructive">
              {jobsErrorText(confirm.error)}
            </p>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={confirm.isPending}>
              {intl.formatMessage({
                id: "jobs_confirm_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={confirm.isPending}
              onClick={(event) => {
                event.preventDefault()
                void confirm
                  .mutateAsync()
                  .then(() => setOpen(false))
                  .catch(() => undefined)
              }}
            >
              {confirm.isPending ? <Spinner data-icon="inline-start" /> : null}
              {intl.formatMessage({
                id: "jobs_confirm_dialog_confirm_button",
                defaultMessage: "Confirm",
              })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
