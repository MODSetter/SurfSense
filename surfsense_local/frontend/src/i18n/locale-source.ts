import { browserLocale } from "./browser-locale"

/** Where the page's language comes from and where a choice is saved. */
export type LocaleSource = NonNullable<
  NonNullable<Window["surfsense"]>["locale"]
>

// Electron's main owns the language on the desktop; without its bridge (the
// Docker image, a browser on `vite`) the browser does (ADR 0075). Read per call,
// since tests install a bridge after this module loads.
export function localeSource(): LocaleSource {
  return window.surfsense?.locale ?? browserLocale
}
