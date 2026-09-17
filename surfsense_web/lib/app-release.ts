/**
 * The desktop release this site links to.
 *
 * Written by `surfsense_local/scripts/bump-version.sh`. It lives here because
 * the web image builds with `context: ./surfsense_web`, so nothing outside
 * this directory exists at build time.
 *
 * Resolved by tag, never through `/releases/latest`, which stays pinned to
 * the legacy 0.0.x app.
 */

export const APP_RELEASE_VERSION = "2.0.0";

export const APP_RELEASE_TAG = `v${APP_RELEASE_VERSION}`;
