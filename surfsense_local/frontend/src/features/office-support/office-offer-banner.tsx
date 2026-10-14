import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { XIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import {
  dismissOfficeOffer,
  getOfficeStatus,
  officeQueryKey,
  type OfficeStatus,
} from "./api"
import { useOfficeOffer } from "./office-offer"

/**
 * Offers Office support under the reply that made an Office file while it is
 * off. It only opens Settings' consent; dismissing it is kept by the API, so
 * no window offers it again.
 */
export function OfficeOfferBanner() {
  const offer = useOfficeOffer()
  const client = useQueryClient()
  const status = useQuery({
    queryKey: officeQueryKey,
    queryFn: ({ signal }) => getOfficeStatus(signal),
  })
  const dismiss = useMutation({
    mutationFn: dismissOfficeOffer,
    onSuccess: (next: OfficeStatus) =>
      client.setQueryData(officeQueryKey, next),
  })
  const office = status.data
  if (
    !offer ||
    !office?.offer ||
    office.offer_dismissed ||
    office.state !== "not_installed" ||
    dismiss.isPending ||
    dismiss.isSuccess
  ) {
    return null
  }
  const title = intl.formatMessage({
    id: "office_support_offer_title",
    defaultMessage: "Office support",
  })
  return (
    <section
      aria-label={title}
      className="mt-3 flex w-full items-start gap-3 rounded-lg border bg-card px-3 py-2.5 text-sm text-card-foreground"
    >
      <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
        <p className="text-pretty">
          {intl.formatMessage(
            {
              id: "office_support_offer_body",
              defaultMessage:
                "Get exact Office pages, real spreadsheet totals and conversion to PDF: download Office support ({size, number, ::unit/megabyte .})?",
            },
            { size: Math.round(office.offer.size / 1e6) }
          )}
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={offer.openOfficeSupport}
        >
          {intl.formatMessage({
            id: "office_support_offer_turn_on_button",
            defaultMessage: "Turn on Office support",
          })}
        </Button>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="-mt-1 -mr-1 shrink-0 text-muted-foreground"
        aria-label={intl.formatMessage({
          id: "office_support_offer_dismiss_aria",
          defaultMessage: "Dismiss the Office support offer",
        })}
        onClick={() => dismiss.mutate()}
      >
        <XIcon />
      </Button>
    </section>
  )
}
