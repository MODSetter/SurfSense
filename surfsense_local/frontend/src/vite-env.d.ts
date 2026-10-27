/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  /** "docker" in the Docker image's build; read it as IN_CONTAINER. */
  readonly VITE_SURFSENSE_RUNTIME?: "docker"
  /** surfsense_local/VERSION, in the Docker image's build. */
  readonly VITE_SURFSENSE_VERSION?: string
}
