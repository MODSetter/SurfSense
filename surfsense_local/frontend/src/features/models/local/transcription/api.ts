import {
  deleteLocalModel,
  getModelCatalog,
  type LocalBuild,
  type LocalRow,
} from "../chat/api"

/** One speech recognition model, as audio.cpp's catalog row offers it. */
export type LocalSpeechModel = {
  /** The row's id: stable, where an install token may be reissued. */
  id: string
  label: string
  curated: boolean
  quantization: string
  size_bytes: number
  peak_mb: number
  detects_language: boolean
  /** ISO 639-1 codes of the languages the model is listed for. */
  languages: string[]
  /** Opaque install token for the build a download fetches. */
  catalog_id: string
  /** What selection and deletion name; null until it is on disk. */
  installed_as: string | null
  /** In use for speech recognition, whatever else names the same build. */
  selected: boolean
  /** What the row's action button reads, marked for this slot alone. */
  build: LocalBuild
}

function toSpeechModel(row: LocalRow): LocalSpeechModel | null {
  // The server picks the build a row leads with: in use, installed, default.
  const lead =
    row.builds.find((b) => b.quantization === row.lead?.quantization) ??
    row.builds[0]
  if (!lead || !row.transcription) return null
  const selected = lead.selected_for
    ? lead.selected_for.includes("speech_to_text")
    : lead.selected
  return {
    id: row.id,
    label: row.name,
    curated: row.origin === "curated",
    quantization: lead.quantization,
    size_bytes: lead.footprint_bytes,
    peak_mb: row.transcription.peak_mb,
    detects_language: row.transcription.detects_language,
    languages: row.transcription.languages,
    catalog_id: lead.catalog_id,
    installed_as: lead.installed_as,
    selected,
    build: { ...lead, selected },
  }
}

/** Empty where no audio.cpp shipped, or it cannot transcribe. */
export async function getLocalSpeechModels(
  signal?: AbortSignal
): Promise<LocalSpeechModel[]> {
  const catalog = await getModelCatalog(signal)
  return (catalog.rows ?? [])
    .filter((row) => row.selectable_for.includes("speech_to_text"))
    .map(toSpeechModel)
    .filter((model): model is LocalSpeechModel => model !== null)
}

export async function deleteLocalSpeechModel(
  installedAs: string
): Promise<void> {
  await deleteLocalModel(installedAs)
}
