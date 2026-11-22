const LATEST_DOWNLOAD = "https://github.com/MODSetter/SurfSense/releases/latest/download";
// Real manifests are about 500 bytes.
const MAX_MANIFEST_CHARS = 64 * 1024;

export type FetchManifest = (
	url: string,
	init: RequestInit & { next?: { revalidate?: number } }
) => Promise<Response>;

/**
 * The channel file of the latest published release. "latest" only moves on
 * publish, so a draft merged to main early is never served. Each revalidation
 * is still a download, so 15 minutes of caching adds about 96 a day per file
 * (more if Vercel caches per region) to GitHub's stable*.yml counts.
 */
export async function fetchLatestGithubManifest(
	file: string,
	fetchManifest: FetchManifest
): Promise<string> {
	const response = await fetchManifest(`${LATEST_DOWNLOAD}/${file}`, {
		redirect: "follow",
		next: { revalidate: 900 },
		// Well inside the app's 10 s, so it still has time to fall back to GitHub.
		signal: AbortSignal.timeout(5000),
	});
	if (response.status !== 200) throw new Error(`GitHub answered ${response.status}`);
	const text = await response.text();
	if (text.length > MAX_MANIFEST_CHARS) throw new Error("manifest is too large");
	return text;
}
