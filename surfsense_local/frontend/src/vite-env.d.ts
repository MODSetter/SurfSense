/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  /** "docker" in the Docker image's build. */
  readonly VITE_SURFSENSE_RUNTIME?: string
}
