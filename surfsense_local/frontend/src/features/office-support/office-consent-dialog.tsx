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
import { intl } from "@/i18n/intl"

import type { OfficeOffer } from "./api"

/**
 * The one consent for the download: it names who makes LibreOffice, the host
 * it comes from, its size and what is sent, so allowing it here also allows
 * that host in Settings › Network (ADR 0027).
 */
export function OfficeConsentDialog({
  offer,
  open,
  onOpenChange,
  onDownload,
}: {
  offer: OfficeOffer
  open: boolean
  onOpenChange: (open: boolean) => void
  onDownload: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage({
              id: "office_support_consent_title",
              defaultMessage: "Download LibreOffice?",
            })}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {intl.formatMessage(
              {
                id: "office_support_consent_body",
                defaultMessage:
                  "SurfSense downloads LibreOffice {version} ({size, number, ::unit/megabyte .}), made by The Document Foundation, from {host}, which may hand the download to one of its mirrors. It sends your IP address and the file’s name, nothing else. LibreOffice then runs on this computer only, to lay out Word and PowerPoint pages exactly, recalculate workbook totals and convert documents to PDF.",
              },
              {
                version: offer.version,
                size: Math.round(offer.size / 1e6),
                host: offer.host,
              }
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            {intl.formatMessage({
              id: "office_support_consent_cancel_button",
              defaultMessage: "Not now",
            })}
          </AlertDialogCancel>
          <AlertDialogAction onClick={onDownload}>
            {intl.formatMessage({
              id: "office_support_consent_download_button",
              defaultMessage: "Download",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
