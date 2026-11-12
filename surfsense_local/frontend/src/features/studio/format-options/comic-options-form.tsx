import { useId } from "react"

import { Select } from "@/components/ui/select"
import { intl } from "@/i18n/intl"

import { ComicKindPicker } from "./comic-kind-picker"
import { type ComicKind, MAX_COMIC_PAGES } from "./comic-kinds"

const PAGE_COUNTS = Array.from({ length: MAX_COMIC_PAGES }, (_, i) => i + 1)

/** The kind of comic and how many pictures it draws, with what that costs. */
export function ComicOptionsForm({
  kind,
  pages,
  onKindChange,
  onPagesChange,
}: {
  kind: ComicKind
  pages: number
  onKindChange: (kind: ComicKind) => void
  onPagesChange: (pages: number) => void
}) {
  const id = useId()
  return (
    <div className="space-y-3">
      <ComicKindPicker value={kind} onChange={onKindChange} />
      <div className="space-y-1">
        <label
          htmlFor={`${id}-pages`}
          className="text-xs font-medium text-muted-foreground"
        >
          {intl.formatMessage({
            id: "studio_comic_pages_label",
            defaultMessage: "Pages",
          })}
        </label>
        <div className="flex items-center gap-3">
          <div className="w-20 shrink-0">
            <Select
              id={`${id}-pages`}
              value={String(pages)}
              onChange={(event) => onPagesChange(Number(event.target.value))}
            >
              {PAGE_COUNTS.map((count) => (
                <option key={count} value={count}>
                  {intl.formatNumber(count)}
                </option>
              ))}
            </Select>
          </div>
          <p className="text-xs text-muted-foreground">
            {intl.formatMessage(
              {
                id: "studio_comic_cost_body",
                defaultMessage:
                  "Draws {count, plural, one {# picture} other {# pictures}} with your image model. Each is billed by its provider, or takes minutes on this computer.",
              },
              { count: pages }
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
