import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { CheckIcon, CopyIcon, ExternalLinkIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { carriesData } from "./carries-data"
import { openConfirmedLink } from "./open-confirmed-link"

function parsed(url: string): URL | null {
  try {
    return new URL(url)
  } catch {
    return null
  }
}

/**
 * Asked before a link from content opens: a chat reply, a Studio document, a tool's
 * result. A link's text can hide its address, and a model can be led to write one
 * that carries the conversation, so the host and the whole address show first.
 */
export function ExternalLinkDialog({
  url,
  open,
  onOpenChange,
}: {
  url: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [copied, setCopied] = useState(false)
  const address = parsed(url)
  // Only https opens; any other address can still be copied.
  const opens = address?.protocol === "https:"
  const copy = async () => {
    await navigator.clipboard.writeText(url)
    setCopied(true)
  }
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={(isOpen) => {
        if (!isOpen) setCopied(false)
      }}
    >
      <DialogContent className="sm:max-w-md">
        {/* The title and the line under it are chrome; only the address is to copy. */}
        <DialogHeader className="select-none">
          <DialogTitle>
            {address
              ? intl.formatMessage(
                  {
                    id: "external_links_dialog_title",
                    defaultMessage: "Open {host}?",
                  },
                  { host: address.host }
                )
              : intl.formatMessage({
                  id: "external_links_dialog_unknown_title",
                  defaultMessage: "Open this link?",
                })}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "external_links_dialog_body",
              defaultMessage:
                "It opens in your browser, outside SurfSense. Check the address first.",
            })}
          </DialogDescription>
        </DialogHeader>
        <p className="max-h-32 overflow-y-auto rounded-md bg-muted px-3 py-2 font-mono text-xs break-all select-text">
          {url}
        </p>
        {address && carriesData(address) ? (
          <p role="alert" className="text-sm text-destructive">
            {intl.formatMessage(
              {
                id: "external_links_dialog_data_body",
                defaultMessage:
                  "This address carries information. Only open it if you trust {host}.",
              },
              { host: address.host }
            )}
          </p>
        ) : null}
        <div className="grid grid-cols-2 gap-2">
          <Button type="button" variant="outline" onClick={() => void copy()}>
            {copied ? (
              <CheckIcon data-icon="inline-start" />
            ) : (
              <CopyIcon data-icon="inline-start" />
            )}
            {copied
              ? intl.formatMessage({
                  id: "external_links_dialog_copied_button",
                  defaultMessage: "Copied",
                })
              : intl.formatMessage({
                  id: "external_links_dialog_copy_button",
                  defaultMessage: "Copy link",
                })}
          </Button>
          <Button
            type="button"
            disabled={!opens}
            onClick={() => {
              openConfirmedLink(url)
              onOpenChange(false)
            }}
          >
            {intl.formatMessage({
              id: "external_links_dialog_open_button",
              defaultMessage: "Open link",
            })}
            <ExternalLinkIcon data-icon="inline-end" />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
