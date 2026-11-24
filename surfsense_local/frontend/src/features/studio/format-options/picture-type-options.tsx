import { useState } from "react"

import type { StudioFormat } from "../api"
import { pictureTypes } from "../picture-types"
import type { FormatOptions } from "./format-options"
import { PictureTypePicker } from "./picture-type-picker"

/** The Image card makes the picture type chosen in its dialog, Image first. */
export function usePictureTypeOptions(
  format: string,
  catalog: StudioFormat[]
): FormatOptions | null {
  const [type, setType] = useState(format)
  if (format !== "image") return null

  const types = pictureTypes(catalog)
  if (types.length < 2) return null
  return {
    panel: <PictureTypePicker types={types} value={type} onChange={setType} />,
    job: { format: type },
    ready: types.some((entry) => entry.key === type && entry.available),
  }
}
