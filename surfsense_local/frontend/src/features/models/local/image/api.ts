import { deleteLocalModel, getModelCatalog, type LocalRow } from "../chat/api"

/** sd.cpp's catalog rows, the same shape chat's are. Empty where no sd-server
 *  is staged: the API then offers no image rows. */
export async function getLocalImageRows(
  signal?: AbortSignal
): Promise<LocalRow[]> {
  const catalog = await getModelCatalog(signal)
  return (catalog.rows ?? []).filter((row) => row.engine === "sdcpp")
}

export function deleteLocalImageModel(installedAs: string) {
  return deleteLocalModel(installedAs)
}
