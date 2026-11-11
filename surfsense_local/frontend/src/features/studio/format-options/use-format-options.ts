import type { StudioFormat } from "../api"
import type { FormatOptions } from "./format-options"
import { usePictureTypeOptions } from "./picture-type-options"
import { usePodcastOptions } from "./podcast-options"

/** The chosen format's own options, or none: a format with options adds its hook here. */
export function useFormatOptions(
  format: string,
  workspaceId: number,
  catalog: StudioFormat[],
  onSetUpVoices: () => void
): FormatOptions {
  // Every hook runs on every render; each answers only for its own format.
  const podcast = usePodcastOptions(format, workspaceId, onSetUpVoices)
  const picture = usePictureTypeOptions(format, catalog)
  return podcast ?? picture ?? { panel: null, job: { format }, ready: true }
}
