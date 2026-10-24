/**
 * Docs URLs across the 2.0 pivot.
 *
 * Until the pivot every page sat directly under `/docs`. Those URLs are
 * indexed and linked from the READMEs, so they move permanently into the
 * version folder rather than 404ing.
 *
 * Kept out of `next.config.ts` because that module cannot be imported from a
 * test: `createMDX()` spawns esbuild on load. `tests/unit/docs-redirects.test.ts`
 * asserts these patterns against real path matching.
 */

/**
 * Path segment for the docs written before the pivot. The sidebar label lives
 * in `content/docs/legacy/meta.json` and reads "SurfSense 0.0.40"; the segment
 * stays version-free so patch releases do not each strand a URL.
 */
export const LEGACY_DOCS_PATH = "legacy";

/** Path segment that bare `/docs` points at, labelled "SurfSense 2.0". */
export const CURRENT_DOCS_PATH = "v2";

/** Segments that are version folders rather than pages, so never re-prefixed. */
const versionSegments = [LEGACY_DOCS_PATH, CURRENT_DOCS_PATH];

// Skip paths that are already a version folder, and paths ending in a file
// extension -- those are screenshots under `public/docs`, and redirects run
// before the public directory is consulted, so without the guard every docs
// image 404s.
const notAVersion = versionSegments.map((segment) => `(?!${segment}(?:/|$))`).join("");
const notAnAsset = "(?!.*\\.[a-z0-9]+$)";

export const docsRedirects = [
	// Deliberately temporary: `/docs` tracks whichever version is current, and
	// a permanent redirect would hand the front door's link equity to a URL
	// that changes with every major release.
	{ source: "/docs", destination: `/docs/${CURRENT_DOCS_PATH}`, permanent: false },
	{
		source: `/docs/:path(${notAVersion}${notAnAsset}.*)`,
		destination: `/docs/${LEGACY_DOCS_PATH}/:path`,
		permanent: true,
	},
];
