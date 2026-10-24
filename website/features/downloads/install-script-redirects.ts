/**
 * The one-line installers: `curl -fsSL https://www.surfsense.com/install.sh | sh`
 * and `irm https://www.surfsense.com/install.ps1 | iex`.
 *
 * Each script ships as an asset of every desktop release, and each resolves
 * the release tag itself before it downloads anything, so these only have to
 * reach the newest copy. Temporary, because Latest moves with every release.
 * The scripts' source is `surfsense_local/packaging/install/`.
 *
 * Kept out of `next.config.ts`, like `docs-redirects.ts`, so a test can import
 * them (`features/downloads/install-script-redirects.test.ts`).
 */

const LATEST_DOWNLOAD = "https://github.com/MODSetter/SurfSense/releases/latest/download";

export const installScriptRedirects = ["install.sh", "install.ps1"].map((script) => ({
	source: `/${script}`,
	destination: `${LATEST_DOWNLOAD}/${script}`,
	permanent: false,
}));
