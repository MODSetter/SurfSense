import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ExternalLinkIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { Connection } from "../api"
import {
  CLAUDE_INSTALL_URL,
  ClaudeHostDeclinedError,
  claudeStatusQueryKey,
  connectClaude,
  getClaudeStatus,
  type ClaudeStatus,
} from "./api"

function openInstallGuide() {
  if (window.surfsense?.openExternal)
    void window.surfsense.openExternal(CLAUDE_INSTALL_URL)
  else window.open(CLAUDE_INSTALL_URL, "_blank", "noopener")
}

/** What to do next, for each state Claude Code can be in. */
function StateBody({ option }: { option: ClaudeStatus }) {
  switch (option.state) {
    case "not_installed":
      return (
        <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm">
          <li>
            {intl.formatMessage({
              id: "models_claude_dialog_install_body",
              defaultMessage: "Install Claude Code on this computer.",
            })}
          </li>
          <li>
            {intl.formatMessage({
              id: "models_claude_dialog_sign_in_body",
              defaultMessage:
                "Open a terminal, run claude, and sign in with your Claude account.",
            })}
          </li>
          <li>
            {intl.formatMessage({
              id: "models_claude_dialog_come_back_body",
              defaultMessage: "Then come back here and click Check again.",
            })}
          </li>
        </ol>
      )
    case "signed_out":
      return (
        <p className="text-sm">
          {intl.formatMessage({
            id: "models_claude_dialog_signed_out_body",
            defaultMessage:
              "Claude Code is installed but not signed in to a Claude plan. Open a terminal, run claude, and sign in.",
          })}
        </p>
      )
    case "too_old":
      return (
        <p className="text-sm">
          {option.version
            ? intl.formatMessage(
                {
                  id: "models_claude_dialog_too_old_body",
                  defaultMessage:
                    "Claude Code {version} is too old for SurfSense. Update it, then check again.",
                },
                { version: option.version }
              )
            : intl.formatMessage({
                id: "models_claude_dialog_unreadable_version_body",
                defaultMessage:
                  "SurfSense couldn’t read which Claude Code is installed. Update it, then check again.",
              })}
        </p>
      )
    case "ready":
      return (
        <p className="text-sm">
          {intl.formatMessage(
            {
              id: "models_claude_dialog_ready_body",
              defaultMessage:
                "Connected as {email}, {plan, select, pro {Pro plan} max {Max plan} team {Team plan} other {Claude plan}}. Claude models then work in chat, Agentic mode, titles and Studio.",
            },
            { email: option.email ?? "", plan: option.plan ?? "other" }
          )}
        </p>
      )
  }
}

/**
 * The Claude plan, set up from the user's own Claude Code. SurfSense cannot
 * sign anyone in to Claude, so this says what Claude Code needs and checks it
 * again on request; nothing polls, since nothing changes until the user acts
 * in their terminal.
 */
export function ClaudeDialog({
  open,
  onOpenChange,
  onConnected,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConnected: (connection: Connection) => void
}) {
  const option = useQuery({
    queryKey: claudeStatusQueryKey,
    queryFn: ({ signal }) => getClaudeStatus(signal),
    enabled: open,
    // Read again on each opening: the user may have just signed in.
    refetchOnMount: "always",
    retry: false,
  })
  const [connecting, setConnecting] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)

  const connect = async () => {
    setConnecting(true)
    setFailure(null)
    try {
      const connection = await connectClaude(
        intl.formatMessage({
          id: "models_claude_connection_label",
          defaultMessage: "Claude plan",
        })
      )
      onConnected(connection)
      onOpenChange(false)
    } catch (error) {
      setFailure(
        error instanceof ClaudeHostDeclinedError
          ? intl.formatMessage(
              {
                id: "models_claude_dialog_host_declined_error",
                defaultMessage:
                  "Your Claude plan needs {host}. Allow it to connect.",
              },
              { host: error.host }
            )
          : error instanceof Error
            ? error.message
            : null
      )
    } finally {
      setConnecting(false)
    }
  }

  const ready = option.data?.state === "ready"
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={(open) => !open && setFailure(null)}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage({
              id: "models_claude_dialog_title",
              defaultMessage: "Use your Claude plan",
            })}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "models_claude_dialog_body",
              defaultMessage:
                "SurfSense uses your Claude Pro, Max or Team plan through Claude Code on this computer. Your sign-in stays in Claude Code, and SurfSense never sees it. Use counts toward your plan’s limits, as it does in Claude Code.",
            })}
          </DialogDescription>
        </DialogHeader>
        {option.isPending ? (
          <Spinner
            aria-label={intl.formatMessage({
              id: "models_claude_dialog_checking_status",
              defaultMessage: "Checking Claude Code",
            })}
          />
        ) : option.data ? (
          <StateBody option={option.data} />
        ) : (
          <p role="alert" className="text-sm text-destructive">
            {intl.formatMessage({
              id: "models_claude_dialog_check_error",
              defaultMessage: "Couldn’t check Claude Code on this computer.",
            })}
          </p>
        )}
        {failure ? (
          <p role="alert" className="text-sm text-destructive">
            {failure}
          </p>
        ) : null}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {intl.formatMessage({
              id: "models_claude_dialog_cancel_button",
              defaultMessage: "Cancel",
            })}
          </Button>
          {option.data?.state === "not_installed" ? (
            <Button type="button" variant="outline" onClick={openInstallGuide}>
              {intl.formatMessage({
                id: "models_claude_dialog_install_guide_button",
                defaultMessage: "Open install guide",
              })}
              <ExternalLinkIcon data-icon="inline-end" />
            </Button>
          ) : null}
          {ready ? (
            <Button
              type="button"
              disabled={connecting}
              onClick={() => void connect()}
            >
              {connecting ? <Spinner data-icon="inline-start" /> : null}
              {intl.formatMessage({
                id: "models_claude_dialog_add_button",
                defaultMessage: "Add Claude models",
              })}
            </Button>
          ) : (
            <Button
              type="button"
              disabled={option.isFetching}
              onClick={() => void option.refetch()}
            >
              {option.isFetching ? <Spinner data-icon="inline-start" /> : null}
              {intl.formatMessage({
                id: "models_claude_dialog_check_again_button",
                defaultMessage: "Check again",
              })}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
