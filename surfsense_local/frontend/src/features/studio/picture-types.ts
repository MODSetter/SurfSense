import type { StudioFormat } from "./api"

// An infographic is offered as a type of image, not a card of its own. Each type
// still makes its own format, so its edits and the agent's tool see no change.
export const PICTURE_TYPES = ["image", "infographic"] as const

export type PictureType = (typeof PICTURE_TYPES)[number]

/** The catalog's entry for each picture type it offers, in the picker's order. */
export function pictureTypes(catalog: StudioFormat[]): StudioFormat[] {
  return PICTURE_TYPES.flatMap(
    (key) => catalog.find((entry) => entry.key === key) ?? []
  )
}

/** The cards Studio shows: an infographic only when there is no image to hold it. */
export function formatCards(catalog: StudioFormat[]): StudioFormat[] {
  if (!catalog.some((entry) => entry.key === "image")) return catalog
  return catalog.filter((entry) => entry.key !== "infographic")
}
