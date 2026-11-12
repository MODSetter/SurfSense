import {
  type ComponentType,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"

import { Button } from "@/components/ui/button"
import {
  BandeDessineeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ComicStripIcon,
  GraphicNovelIcon,
  MangaIcon,
  ManhuaIcon,
  PictureBookIcon,
  StoryboardIcon,
  WebtoonIcon,
  WesternComicIcon,
  YonkomaIcon,
} from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { COMIC_KINDS, type ComicKind } from "./comic-kinds"
import { PictureCard } from "./picture-card"

const KIND_ART: Record<ComicKind, ComponentType<{ className?: string }>> = {
  western: WesternComicIcon,
  graphic_novel: GraphicNovelIcon,
  bande_dessinee: BandeDessineeIcon,
  manga: MangaIcon,
  manhua: ManhuaIcon,
  webtoon: WebtoonIcon,
  comic_strip: ComicStripIcon,
  yonkoma: YonkomaIcon,
  picture_book: PictureBookIcon,
  storyboard: StoryboardIcon,
}

/** Every kind of comic as a card in one row that scrolls sideways; an arrow
 *  shows on a side only while more kinds lie that way. */
export function ComicKindPicker({
  value,
  onChange,
}: {
  value: ComicKind
  onChange: (kind: ComicKind) => void
}) {
  const row = useRef<HTMLDivElement>(null)
  const [more, setMore] = useState({ back: false, ahead: false })

  const measure = useCallback(() => {
    const element = row.current
    if (!element) return
    setMore({
      // A few pixels of slack: the snap settles within the row's padding.
      back: element.scrollLeft > 4,
      ahead: element.scrollLeft + element.clientWidth < element.scrollWidth - 4,
    })
  }, [])

  useEffect(() => {
    measure()
    const element = row.current
    if (!element || typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [measure])

  const page = (direction: 1 | -1) => {
    const element = row.current
    if (!element) return
    const still = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)"
    ).matches
    element.scrollBy({
      left: direction * element.clientWidth * 0.8,
      behavior: still ? "auto" : "smooth",
    })
  }

  const label = intl.formatMessage({
    id: "studio_comic_kind_label",
    defaultMessage: "Kind",
  })
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {/* Sized by the dialog, not by its ten cards: a grid or flex parent would
          otherwise grow to fit the whole row instead of letting it scroll. */}
      <div className="relative [contain:inline-size]">
        <ScrollFade
          orientation="horizontal"
          ref={row}
          role="radiogroup"
          aria-label={label}
          onScroll={measure}
          viewportClassName="flex snap-x scroll-px-0.5 [scrollbar-width:none] gap-2 p-0.5 [&::-webkit-scrollbar]:hidden"
        >
          {COMIC_KINDS.map((kind) => (
            <PictureCard
              key={kind.key}
              name="studio-comic-kind"
              value={kind.key}
              label={kind.label()}
              Art={KIND_ART[kind.key]}
              checked={value === kind.key}
              className="w-32 shrink-0 snap-start"
              onChange={(event) => {
                onChange(kind.key)
                // A kind reached by the arrow keys comes into view.
                event.currentTarget
                  .closest("label")
                  ?.scrollIntoView?.({ block: "nearest", inline: "nearest" })
              }}
            />
          ))}
        </ScrollFade>
        <ScrollArrow side="back" shown={more.back} onClick={() => page(-1)} />
        <ScrollArrow side="ahead" shown={more.ahead} onClick={() => page(1)} />
      </div>
    </div>
  )
}

function ScrollArrow({
  side,
  shown,
  onClick,
}: {
  side: "back" | "ahead"
  shown: boolean
  onClick: () => void
}) {
  if (!shown) return null
  const Icon = side === "back" ? ChevronLeftIcon : ChevronRightIcon
  return (
    <Button
      type="button"
      variant="default"
      size="icon-sm"
      // Pointer only: the arrow keys already move through the kinds.
      tabIndex={-1}
      aria-label={
        side === "back"
          ? intl.formatMessage({
              id: "studio_comic_kind_scroll_back_aria",
              defaultMessage: "Show earlier kinds",
            })
          : intl.formatMessage({
              id: "studio_comic_kind_scroll_ahead_aria",
              defaultMessage: "Show more kinds",
            })
      }
      onClick={onClick}
      className={cn(
        // Centred on the cards' pictures, which are 2/3 of a 128 px card wide.
        "absolute top-[calc(128px/3-12px)] rounded-full shadow-md",
        side === "back" ? "-left-2" : "-right-2"
      )}
    >
      <Icon />
    </Button>
  )
}
