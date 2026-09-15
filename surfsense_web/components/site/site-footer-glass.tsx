"use client";

import { FlutedGlass } from "@paper-design/shaders-react";

/**
 * The fluted-glass texture behind the footer panel.
 *
 * `FlutedGlass` is a WebGL shader: it draws parallel vertical prisms and lights
 * them from one side, which is what turns the footer's flat dark panel into a
 * ribbed surface. Nothing is sampled from the page behind it — the panel paints
 * its own ground and this sits on top, adding only highlight and shadow.
 *
 * The only client component in the footer, which is why it is split out: the
 * footer itself stays a server component and ships no JavaScript of its own.
 *
 * The colours are deliberately low-contrast. The site is dark and the panel is
 * warm charcoal; a strong highlight would read as a striped background rather
 * than as a material, and would fight the link columns sitting over it.
 */
export function SiteFooterGlass() {
	return (
		<FlutedGlass
			size={0.89}
			shape="lines"
			angle={0}
			distortionShape="prism"
			distortion={0.5}
			shift={0}
			blur={0}
			edges={0.25}
			stretch={0}
			scale={1.11}
			fit="cover"
			highlights={0.08}
			shadows={0.22}
			grainMixer={0.12}
			grainOverlay={0.1}
			colorBack="#00000000"
			colorHighlight="#e8e3da"
			colorShadow="#000000"
			style={{ width: "100%", height: "100%" }}
		/>
	);
}
