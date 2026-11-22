// The operating system's own switch for SurfSense's microphone, apart from the
// page's permission (permissions/media.ts). Mirrored in frontend/src/lib/api.ts.
export type MicrophoneAccess = ReturnType<
  Electron.SystemPreferences["getMediaAccessStatus"]
>

/** What the main process reads and opens on the system it runs on. */
export type SystemMicrophone = {
  platform: NodeJS.Platform
  preferences: Pick<
    Electron.SystemPreferences,
    "getMediaAccessStatus" | "askForMediaAccess"
  >
  openExternal: (url: string) => Promise<void>
}

// Neither is https, so neither passes allowedExternalUrl; the page never names them.
const SETTINGS_PAGES: Partial<Record<NodeJS.Platform, string>> = {
  win32: "ms-settings:privacy-microphone",
  darwin:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}

export function microphoneAccess(system: SystemMicrophone): MicrophoneAccess {
  // An AppImage or a deb has no switch to read: getUserMedia's own error says the rest.
  if (system.platform !== "win32" && system.platform !== "darwin")
    return "granted"
  return system.preferences.getMediaAccessStatus("microphone")
}

/** macOS asks once, before getUserMedia, which alone does not always prompt a packaged app. */
export async function askForMicrophone(
  system: SystemMicrophone
): Promise<MicrophoneAccess> {
  if (system.platform === "darwin") {
    await system.preferences.askForMediaAccess("microphone")
  }
  return microphoneAccess(system)
}

/** Whether the system's microphone settings were opened; Linux has none to open. */
export async function openMicrophoneSettings(
  system: SystemMicrophone
): Promise<boolean> {
  const page = SETTINGS_PAGES[system.platform]
  if (page === undefined) return false
  try {
    await system.openExternal(page)
    return true
  } catch {
    return false
  }
}
