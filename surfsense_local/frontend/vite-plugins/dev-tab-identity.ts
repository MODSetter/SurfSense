import type { Plugin } from "vite"

/** The dev server's tab says SurfSense Dev and wears the DEV icon, as Electron's
 *  dev build does (dev-app-identity.ts), so the Docker dev stack is told apart
 *  from an install. Both icons are cut from electron/build/icons' 512 px PNGs,
 *  which the Docker build cannot read. */
export function devTabIdentity(): Plugin {
  return {
    name: "dev-tab-identity",
    apply: "serve",
    transformIndexHtml: (html) =>
      html
        .replace('href="./favicon.ico"', 'href="./favicon-dev.ico"')
        .replace("<title>SurfSense</title>", "<title>SurfSense Dev</title>"),
  }
}
