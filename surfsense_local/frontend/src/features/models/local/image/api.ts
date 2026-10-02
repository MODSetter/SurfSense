import { requestJson } from "@/lib/api"

import type { ModelType } from "../../model-type"
import { deleteLocalModel, getModelCatalog, type LocalRow } from "../chat/api"

/** The slots sd-server fills: images, editing them, and video. */
export type SdCppSlot = Extract<
  ModelType,
  "image_gen" | "image_edit" | "video_gen"
>

/** sd.cpp's catalog rows that can fill `slot`, the same shape chat's are, each
 *  build marked in use for that slot only: FLUX.2 klein in use for images is
 *  still to choose for editing. Empty where no sd-server is staged. */
export async function getLocalImageRows(
  slot: SdCppSlot,
  signal?: AbortSignal
): Promise<LocalRow[]> {
  const catalog = await getModelCatalog(signal)
  return (catalog.rows ?? [])
    .filter(
      (row) => row.engine === "sdcpp" && row.selectable_for.includes(slot)
    )
    .map((row) => ({
      ...row,
      builds: row.builds.map((build) => ({
        ...build,
        selected: build.selected_for
          ? build.selected_for.includes(slot)
          : build.selected,
      })),
    }))
}

export function deleteLocalImageModel(installedAs: string) {
  return deleteLocalModel(installedAs)
}

/** What the chosen local model's sd-server is doing. `idle`: it starts when
 *  Studio needs it; `missing`: a file is gone, so it cannot start. */
export type ImageServerState = "none" | "idle" | "running" | "missing"

export async function getLocalImageState(
  slot: SdCppSlot,
  signal?: AbortSignal
): Promise<ImageServerState> {
  const reply = await requestJson<{ state: ImageServerState }>(
    `/llm/image/local/state?model_type=${slot}`,
    { signal }
  )
  return reply.state
}
