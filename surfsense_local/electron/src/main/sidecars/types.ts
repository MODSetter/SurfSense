/** One child the supervisor spawns and reaps: what to run and the env it needs. */
export interface SidecarSpec {
  name: string
  cmd: string
  args: string[]
  cwd: string
  /** Extra env, merged over process.env by the supervisor. */
  env: Record<string, string>
}

/** Called when a sidecar exits without us asking it to. */
export type CrashHandler = (name: string, code: number | null) => void

/** Everything the spec builders read; index.ts assembles it once per boot. */
export interface SidecarContext {
  packaged: boolean
  /** Dev cwd for `uv run`. */
  backendDir: string
  /** resources/ root in the packaged app; where binaries are unpacked. */
  binariesDir: string
  host: string
  apiPort: number
  dataDir: string
  /** Packaged: read-only bundled embedding model. */
  modelsDir?: string
  /** Packaged: writable Hugging Face cache for Docling's first-run download. */
  hfHome?: string
  /** Packaged: the bundled Ollama's port, model dir, and URL for the API. */
  ollamaPort?: number
  ollamaModelsDir?: string
  ollamaUrl?: string
}
