import { FieldDescription } from "@/components/ui/field"
import { ExternalLinkIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

const CONSOLE_URL = "https://opencode.ai/console"
const OPENCODE_PROVIDER = "opencode"
const OPENCODE_GO_PROVIDER = "opencode-go"

export function OpencodeKeyHint({ providerId }: { providerId: string }) {
  if (providerId !== OPENCODE_PROVIDER && providerId !== OPENCODE_GO_PROVIDER)
    return null
  return (
    <FieldDescription>
      <a
        href={CONSOLE_URL}
        target="_blank"
        rel="noreferrer"
        // The desktop app refuses in-app navigation: the page opens in the OS
        // browser through the bridge. A bare browser follows href.
        onClick={(event) => {
          if (!window.surfsense?.openExternal) return
          event.preventDefault()
          void window.surfsense.openExternal(CONSOLE_URL)
        }}
        className="inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline"
      >
        {intl.formatMessage({
          id: "models_connection_form_opencode_key_link",
          defaultMessage: "Get your key in the OpenCode Console",
        })}
        <ExternalLinkIcon className="size-3.5" />
      </a>
      {providerId === OPENCODE_GO_PROVIDER ? (
        <>
          {" "}
          {intl.formatMessage({
            id: "models_connection_form_opencode_go_subscription_body",
            defaultMessage: "The key’s workspace needs a Go subscription.",
          })}
        </>
      ) : null}
    </FieldDescription>
  )
}
