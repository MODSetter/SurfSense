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
  /** Per-install secret the backend encrypts provider API keys with. */
  secret: string
  /** Packaged: read-only bundled embedding, voice, and Docling parser packs. */
  modelsDir?: string
  /**
   * llama-server's router port, models dir, and URL for API + worker.
   *
   * Set in dev and packaged both: only `llamacppBinariesDir` differs between
   * them, the same way `modelsDir` and the Python sidecars already work.
   */
  llamacppPort?: number
  llamacppModelsDir?: string
  llamacppUrl?: string
  /**
   * Where the staged llama.cpp build lives.
   *
   * The backend needs this as well as Electron: its hardware probe loads ggml
   * by ctypes and must run from this directory, because ggml scans the running
   * executable's own directory for backends and silently finds none anywhere
   * else. Unset, every machine badges as having no GPU and nothing says why.
   */
  llamacppBinariesDir?: string
  /** Packaged: the bundled sd-server's port, model dir, and URL for API + worker. */
  imagePort?: number
  imageModelsDir?: string
  imageUrl?: string
  /** audio.cpp's server: its port and URL, the audio models folder, and its staged build. */
  audioPort?: number
  audioUrl?: string
  audioModelsDir?: string
  audioBinariesDir?: string
}
