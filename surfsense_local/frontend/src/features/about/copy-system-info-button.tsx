import { Button } from "@/components/ui/button"
import { CheckIcon, CopyIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { useCopyToClipboard } from "./use-copy-to-clipboard"

export function CopySystemInfoButton({ text }: { text: string }) {
  const { copied, copy } = useCopyToClipboard(text)

  return (
    <Button type="button" variant="outline" onClick={() => void copy()}>
      {copied ? (
        <CheckIcon data-icon="inline-start" />
      ) : (
        <CopyIcon data-icon="inline-start" />
      )}
      {copied
        ? intl.formatMessage({
            id: "about_system_info_copied_button",
            defaultMessage: "Copied",
          })
        : intl.formatMessage({
            id: "about_system_info_copy_button",
            defaultMessage: "Copy system info",
          })}
    </Button>
  )
}
