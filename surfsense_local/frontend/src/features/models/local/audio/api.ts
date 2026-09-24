import {
  deleteLocalModel,
  getModelCatalog,
  type LocalBuild,
  type LocalRow,
} from "../chat/api"

/** One curated audio model, as audio.cpp's catalog row offers it. */
export type LocalAudioModel = {
  /** The row's id: stable, where an install token may be reissued. */
  id: string
  label: string
  quantization: string
  size_bytes: number
  peak_mb: number
  voice_count: number
  languages: string[]
  /** Opaque install token for the build a download fetches. */
  catalog_id: string
  /** What selection and deletion name; null until it is on disk. */
  installed_as: string | null
  selected: boolean
  /** What the row's action button reads, the same as chat's and image's. */
  build: LocalBuild
}

/** Empty where no audio.cpp shipped: the API then offers no audio rows. */
export type LocalAudioCatalog = {
  provider: "audiocpp"
  models: LocalAudioModel[]
}

function toAudioModel(row: LocalRow): LocalAudioModel | null {
  // The server picks the build a row leads with: in use, installed, default.
  const build =
    row.builds.find((b) => b.quantization === row.lead?.quantization) ??
    row.builds[0]
  if (!build || !row.voicing) return null
  return {
    id: row.id,
    label: row.name,
    quantization: build.quantization,
    size_bytes: build.footprint_bytes,
    peak_mb: row.voicing.peak_mb,
    voice_count: row.voicing.voice_count,
    languages: row.voicing.languages,
    catalog_id: build.catalog_id,
    installed_as: build.installed_as,
    selected: build.selected,
    build,
  }
}

export async function getLocalAudioCatalog(
  signal?: AbortSignal
): Promise<LocalAudioCatalog> {
  const catalog = await getModelCatalog(signal)
  return {
    provider: "audiocpp",
    models: (catalog.rows ?? [])
      .filter((row) => row.engine === "audiocpp")
      .map(toAudioModel)
      .filter((model): model is LocalAudioModel => model !== null),
  }
}

export async function deleteLocalAudioModel(
  installedAs: string
): Promise<void> {
  await deleteLocalModel(installedAs)
}
