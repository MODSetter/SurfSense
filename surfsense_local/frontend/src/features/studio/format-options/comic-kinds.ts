import { intl } from "@/i18n/intl"

// The server's kinds (backend/modules/artifacts/comic/kinds.py), key for key,
// each with the length it starts at.
export const COMIC_KINDS = [
  {
    key: "western",
    pages: 4,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_western_label",
        defaultMessage: "Western comic",
      }),
  },
  {
    key: "graphic_novel",
    pages: 4,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_graphic_novel_label",
        defaultMessage: "Graphic novel",
      }),
  },
  {
    key: "bande_dessinee",
    pages: 4,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_bande_dessinee_label",
        defaultMessage: "Bande dessinée",
      }),
  },
  {
    key: "manga",
    pages: 4,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_manga_label",
        defaultMessage: "Manga",
      }),
  },
  {
    key: "manhua",
    pages: 4,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_manhua_label",
        defaultMessage: "Manhua",
      }),
  },
  {
    key: "webtoon",
    pages: 8,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_webtoon_label",
        defaultMessage: "Webtoon",
      }),
  },
  {
    key: "comic_strip",
    pages: 1,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_comic_strip_label",
        defaultMessage: "Comic strip",
      }),
  },
  {
    key: "yonkoma",
    pages: 1,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_yonkoma_label",
        defaultMessage: "Yonkoma (4-koma)",
      }),
  },
  {
    key: "picture_book",
    pages: 4,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_picture_book_label",
        defaultMessage: "Picture book",
      }),
  },
  {
    key: "storyboard",
    pages: 6,
    label: () =>
      intl.formatMessage({
        id: "studio_comic_kind_storyboard_label",
        defaultMessage: "Storyboard",
      }),
  },
] as const

export type ComicKind = (typeof COMIC_KINDS)[number]["key"]

// Each picture is billed or takes minutes, so a comic stops here.
export const MAX_COMIC_PAGES = 12

export function startingPages(kind: ComicKind): number {
  return COMIC_KINDS.find((entry) => entry.key === kind)?.pages ?? 4
}
