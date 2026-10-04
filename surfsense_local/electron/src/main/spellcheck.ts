// Chromium downloads a Hunspell dictionary from Google's CDN for every
// language in a session's spellchecker list, as soon as the session exists.
// Measured on Electron 44.2.0 on Linux: `webPreferences.spellcheck: false` and
// `setSpellCheckerEnabled(false)` stop the checking and not the download, and
// `webRequest` never sees it. An empty list is what leaves nothing to fetch.
// macOS uses the OS spellchecker, downloads nothing, and ignores the call.
type SpellcheckSession = { setSpellCheckerLanguages(languages: string[]): void }
type SessionCreator = {
  on(event: "session-created", listener: (session: SpellcheckSession) => void): unknown
}

/** Call before `ready`: the default session is created with the app. */
export function refuseSpellcheckDownloads(app: SessionCreator): void {
  app.on("session-created", (session) => session.setSpellCheckerLanguages([]))
}
