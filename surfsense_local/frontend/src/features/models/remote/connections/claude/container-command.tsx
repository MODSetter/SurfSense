import { Button } from "@/components/ui/button"
import { CheckIcon, CopyIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { useCopyToClipboard } from "@/features/about/use-copy-to-clipboard"
import { intl } from "@/i18n/intl"

/** Run on the Docker host, in the folder with docker-compose.yml. The image's HOME
 * is on /data, where the backend looks; pipefail fails the install when the download does. */
export const INSTALL_IN_CONTAINER =
  "docker compose exec surfsense bash -c 'set -o pipefail; curl -fsSL https://claude.ai/install.sh | bash'"
export const SIGN_IN_IN_CONTAINER = "docker compose exec -it surfsense claude"

/** A command to paste into a terminal on the Docker host, copied in one click. */
export function ContainerCommand({ command }: { command: string }) {
  const { copied, copy } = useCopyToClipboard(command)
  return (
    <div className="flex items-center gap-2">
      <Input
        readOnly
        value={command}
        aria-label={intl.formatMessage({
          id: "models_claude_dialog_container_command_label",
          defaultMessage: "Command",
        })}
        className="flex-1 font-mono text-xs select-text"
      />
      <Button
        type="button"
        size="icon-sm"
        variant="ghost"
        data-copied={copied}
        aria-label={intl.formatMessage({
          id: "models_claude_dialog_container_command_copy_aria",
          defaultMessage: "Copy the command",
        })}
        onClick={() => void copy()}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </Button>
    </div>
  )
}
