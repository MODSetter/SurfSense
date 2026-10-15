import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { ChatGptIcon, ExternalLinkIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { ModelType } from "../../../model-type"
import { useRefreshModels } from "../../../models-query"
import { getConnections, type Connection } from "../api"
import { useConnectionsServing } from "../use-connections"
import { getSignInOption, signInOptionQueryKey } from "./api"
import { SignInProgress } from "./sign-in-progress"
import { useChatGPTSignIn } from "./use-sign-in"

/**
 * A ChatGPT plan, offered beside Use a server rather than inside its provider
 * list: one click signs in. Shown only where the backend says a plan fills the
 * slot; a plan already connected opens its models instead of signing in again.
 */
export function ChatGPTOption({
  modelType,
  onConnected,
  dense = false,
}: {
  modelType: ModelType
  onConnected: (connection: Connection) => void
  /** Onboarding's smaller heading and button, beside its own server row. */
  dense?: boolean
}) {
  const option = useQuery({
    queryKey: signInOptionQueryKey,
    queryFn: ({ signal }) => getSignInOption(signal),
    retry: false,
  })
  // The same list as the slot's, so a plan connected anywhere is reused.
  const connections = useConnectionsServing(modelType)
  const refresh = useRefreshModels()
  const { state, start, cancel } = useChatGPTSignIn(async (id) => {
    const saved = (await getConnections()).find((entry) => entry.id === id)
    void refresh()
    if (saved) onConnected(saved)
  })

  if (!option.data?.serves.includes(modelType)) return null

  const connected = connections.data?.find(
    (connection) => connection.auth_kind === "chatgpt"
  )
  const signingIn = state.phase === "starting" || state.phase === "waiting"
  const size = dense ? "default" : "sm"
  const title = intl.formatMessage({
    id: "models_chatgpt_option_title",
    defaultMessage: "Use your ChatGPT plan",
  })

  return (
    <section aria-label={title} className="flex flex-col gap-2">
      {/* Aligned as the Use a server row beside it is; progress shows below, so the button stays put. */}
      <div
        className={cn(
          "flex justify-between",
          dense ? "items-center gap-4" : "items-start gap-3"
        )}
      >
        <div className="min-w-0">
          <h3
            className={cn(
              "flex items-center gap-2 font-medium",
              dense ? "text-sm" : "text-base"
            )}
          >
            <ChatGptIcon
              aria-hidden="true"
              className="size-4 text-muted-foreground"
            />
            {title}
          </h3>
          {/* pl-6: the icon's 16px plus the 8px gap, so it lines up with the heading text. */}
          <p className="truncate pl-6 text-xs text-muted-foreground">
            {connected
              ? intl.formatMessage(
                  {
                    id: "models_chatgpt_option_connected_body",
                    defaultMessage: "Connected as {account}",
                  },
                  { account: connected.account_email ?? connected.label }
                )
              : intl.formatMessage({
                  id: "models_chatgpt_option_body",
                  defaultMessage:
                    "Plus or Pro, with no API key. You sign in in your browser.",
                })}
          </p>
        </div>
        {connected ? (
          <Button
            type="button"
            size={size}
            variant="outline"
            onClick={() => onConnected(connected)}
          >
            {intl.formatMessage({
              id: "models_chatgpt_option_show_button",
              defaultMessage: "Show models",
            })}
          </Button>
        ) : signingIn ? (
          <Button type="button" size={size} variant="outline" onClick={cancel}>
            {intl.formatMessage({
              id: "models_chatgpt_option_cancel_button",
              defaultMessage: "Cancel",
            })}
          </Button>
        ) : (
          <Button
            type="button"
            size={size}
            variant="outline"
            onClick={() =>
              void start({
                label: intl.formatMessage({
                  id: "models_chatgpt_option_connection_label",
                  defaultMessage: "ChatGPT subscription",
                }),
              })
            }
          >
            {intl.formatMessage({
              id: "models_chatgpt_option_sign_in_button",
              defaultMessage: "Sign in with ChatGPT",
            })}
            {/* Sign-in continues in the browser, as "Continue on GitHub" does. */}
            <ExternalLinkIcon data-icon="inline-end" />
          </Button>
        )}
      </div>
      <div className="pl-6 empty:hidden">
        <SignInProgress state={state} />
      </div>
    </section>
  )
}
