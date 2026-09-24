import {
  deleteLocalModel,
  getModelCatalog,
  installCatalogModel,
  type InstallEvent,
  type LocalRow,
} from "../chat/api"

/** One curated image model, as sd.cpp's catalog row offers it. */
export type LocalImageModel = {
  /** The row's id: stable, where an install token may be reissued. */
  id: string
  label: string
  detail: string
  size_bytes: number
  /** Opaque install token for the build a download fetches. */
  catalog_id: string
  /** What selection and deletion name; null until it is on disk. */
  installed_as: string | null
  selected: boolean
}

/** Empty where no sd-server shipped: the API then offers no image rows. */
export type LocalImageCatalog = {
  provider: "sdcpp"
  models: LocalImageModel[]
}

export type DownloadStep = {
  status: string
  completed: number
  total: number
}

function toImageModel(row: LocalRow): LocalImageModel | null {
  // The server picks the build a row leads with: in use, installed, default.
  const build =
    row.builds.find((b) => b.quantization === row.lead?.quantization) ??
    row.builds[0]
  if (!build) return null
  return {
    id: row.id,
    label: row.name,
    detail: build.quantization,
    size_bytes: build.footprint_bytes,
    catalog_id: build.catalog_id,
    installed_as: build.installed_as,
    selected: build.selected,
  }
}

export async function getLocalImageCatalog(
  signal?: AbortSignal
): Promise<LocalImageCatalog> {
  const catalog = await getModelCatalog(signal)
  return {
    provider: "sdcpp",
    models: (catalog.rows ?? [])
      .filter((row) => row.engine === "sdcpp")
      .map(toImageModel)
      .filter((model): model is LocalImageModel => model !== null),
  }
}

export async function deleteLocalImageModel(
  installedAs: string
): Promise<void> {
  await deleteLocalModel(installedAs)
}

/** Downloads without selecting: an image model is picked once it is on disk. */
export async function installLocalImageModel(
  catalogId: string,
  onStep: (step: DownloadStep) => void,
  signal?: AbortSignal
): Promise<void> {
  // Only `downloading` carries byte counts; other phases keep the last ones.
  let last: DownloadStep = { status: "starting", completed: 0, total: 0 }
  const onEvent = (event: InstallEvent) => {
    last =
      event.type === "downloading"
        ? { status: event.type, completed: event.completed, total: event.total }
        : { ...last, status: event.type }
    onStep(last)
  }
  await installCatalogModel(catalogId, onEvent, signal, false)
}
