import { useAuiState } from "@assistant-ui/react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Alert02Icon } from "@/components/ui/icons"
import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"
import { translatedChatError } from "./chat-error-text"
import type { ChatTurnError } from "./use-chat-runtime"

type Action = "model-setup" | "new-chat" | "retry" | "none"

function actionFor(error: ChatTurnError): Action {
  switch (error.kind) {
    case "provider_auth":
    case "subscription_sign_in":
    case "provider_not_found":
    case "model_cannot_run":
      return "model-setup"
    case "network":
      // A bad base URL is a Model setup fix; a local runtime that isn't
      // running isn't — there's no settings action that starts it.
      return error.provider === "llamacpp" ? "none" : "model-setup"
    // A reached plan limit: retrying cannot help until the plan's window resets.
    case "subscription_limit":
    case "context_too_long":
      // The notice text already says to start a new chat or pick a model
      // with a larger window — Retry would resend the same overlong turn.
      return "none"
    // The thread keeps its engine, so only a new thread takes this model.
    case "agent_model_unsupported":
      return "new-chat"
    default:
      return "retry"
  }
}

export function ChatErrorNotice({
  onModelSetup,
  onNewChat,
  onRetry,
}: {
  onModelSetup: () => void
  onNewChat: () => void
  onRetry: (assistantId: string) => void
}) {
  const messageId = useAuiState(({ message }) => message.id)
  const error = useAuiState(({ message }) =>
    message.status?.type === "incomplete" && message.status.reason === "error"
      ? (message.status.error as ChatTurnError | undefined)
      : undefined
  )

  if (!error) {
    return null
  }

  const action = actionFor(error)

  return (
    <Alert variant="destructive" className="mt-2 w-auto">
      <Alert02Icon />
      <AlertDescription className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <span>{translatedChatError(error)}</span>
        {action === "model-setup" ? (
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 text-foreground"
            onClick={onModelSetup}
          >
            {intl.formatMessage({
              id: "chat_failed_reply_model_setup_button",
              defaultMessage: "Model setup",
            })}
          </Button>
        ) : action === "new-chat" ? (
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 text-foreground"
            onClick={onNewChat}
          >
            {intl.formatMessage({
              id: "chat_failed_reply_new_chat_button",
              defaultMessage: "New chat",
            })}
          </Button>
        ) : action === "retry" ? (
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 text-foreground"
            onClick={() => onRetry(messageId)}
          >
            {intl.formatMessage({
              id: "chat_failed_reply_retry_button",
              defaultMessage: "Retry",
            })}
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
