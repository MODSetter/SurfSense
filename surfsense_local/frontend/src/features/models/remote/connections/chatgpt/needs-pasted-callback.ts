const HOST_ITSELF = new Set(["localhost", "127.0.0.1", "[::1]", "::1"])

/**
 * Docker only, on a device other than the host: OpenAI's redirect goes to
 * 127.0.0.1, which there reaches nothing, so the address it leaves is pasted
 * back (docs/proposals/docker/README.md, Sign-ins).
 */
export function needsPastedCallback(): boolean {
  return (
    import.meta.env.VITE_SURFSENSE_RUNTIME === "docker" &&
    !HOST_ITSELF.has(window.location.hostname)
  )
}
