import { mayCaptureMedia, type MediaAsk } from "./media.ts"

type PermissionSession = Pick<
  Electron.Session,
  "setPermissionRequestHandler" | "setPermissionCheckHandler"
>
type SessionCreator = {
  on(
    event: "session-created",
    listener: (session: PermissionSession) => void
  ): unknown
}

/**
 * Electron approves every permission a session has no handler for, so any frame
 * could open the microphone silently. Media is decided by `mayCaptureMedia`;
 * every other permission keeps Electron's own answer, so copying keeps working
 * until a strict allowlist has its own audit.
 *
 * Call before `ready`: the default session is created with the app.
 */
export function installPermissionHandlers(
  app: SessionCreator,
  options: {
    appPage: URL
    isMainWindow: (contents: Electron.WebContents | null) => boolean
  }
): void {
  const answer = (permission: string, media: () => MediaAsk): boolean => {
    if (permission === "media") return mayCaptureMedia(media(), options.appPage)
    if (permission === "display-capture") return false
    // Electron's default when a session has no check handler.
    return permission !== "deprecated-sync-clipboard-read"
  }

  app.on("session-created", (session) => {
    session.setPermissionRequestHandler(
      (contents, permission, callback, details) =>
        callback(
          answer(permission, () => ({
            fromMainWindow: options.isMainWindow(contents),
            isMainFrame: details.isMainFrame,
            requestingUrl: details.requestingUrl,
            mediaTypes:
              "mediaTypes" in details ? (details.mediaTypes ?? []) : [],
          }))
        )
    )
    session.setPermissionCheckHandler(
      (contents, permission, _origin, details) =>
        answer(permission, () => ({
          fromMainWindow: options.isMainWindow(contents),
          isMainFrame: details.isMainFrame,
          requestingUrl: details.requestingUrl,
          mediaTypes:
            details.mediaType === undefined ? [] : [details.mediaType],
        }))
    )
  })
}
