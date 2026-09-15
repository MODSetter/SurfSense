/**
 * The "sources become artifacts" bento cell's illustration.
 *
 * `/public/homepage/artifacts.svg` carries its own SMIL animation (loops on an
 * 11s cycle), so it is referenced as a plain `<img>` rather than inlined —
 * SMIL keeps animating from an `<img>` tag, and inlining fifty-odd KB of
 * generated markup into this file would buy nothing.
 */
export function HomeArtifactIllustration() {
	return (
		// biome-ignore lint/performance/noImgElement: SMIL animation only plays from a real <img>/object; next/image would serve it as a static frame.
		<img src="/homepage/artifacts.svg" alt="" className="ss-home-artifact" aria-hidden="true" />
	);
}
