import type { IllustratedCell } from "@/components/homepage/home/home-content";

/**
 * A bento cell's designed SVG illustration — "No cloud in the loop" and
 * "Sources become artifacts" each carry their own built-in SMIL animation, so
 * they are referenced as plain `<img>` rather than inlined: SMIL keeps
 * animating from an `<img>` tag, and inlining tens of KB of generated markup
 * into this file would buy nothing.
 */
const ILLUSTRATION_SRC: Record<IllustratedCell, string> = {
	"no-cloud": "/homepage/no-cloud-in-the-loop.svg",
	"local-key": "/homepage/local-model-toggle.svg",
	artifacts: "/homepage/artifacts.svg",
};

export function HomeArtifactIllustration({ illustration }: { illustration: IllustratedCell }) {
	return (
		// biome-ignore lint/performance/noImgElement: SMIL animation only plays from a real <img>/object; next/image would serve it as a static frame.
		<img
			src={ILLUSTRATION_SRC[illustration]}
			alt=""
			className="ss-home-artifact"
			aria-hidden="true"
		/>
	);
}
