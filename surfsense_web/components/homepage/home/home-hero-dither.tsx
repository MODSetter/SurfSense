"use client";

import { ImageDithering } from "@paper-design/shaders-react";

/**
 * The hero's dithered backdrop.
 *
 * `ImageDithering` is a WebGL filter: it uploads
 * `public/homepage/cta-dither-background.webp` as a texture and re-renders it
 * through a Bayer matrix, so the artwork arrives as a coarse two-tone stipple
 * rather than a photograph. The source must stay same-origin — a cross-origin
 * URL, `next/image`'s `/_next/image?...` included, taints the canvas — which is
 * why it is referenced as a plain path out of `public/`.
 *
 * The texture is 1200px wide, not the source artwork's 1672px. `size={3}`
 * quantises the output into 3px cells, so the hero samples roughly 383x200 of
 * them and detail beyond that is discarded before anything is drawn. The source
 * PNG was 1973 KB and, being PNG, did not gzip; this WebP is 39 KB for output
 * that is identical once dithered to three colours.
 *
 * The only client component on the landing page. Everything around it stays a
 * server component; this one needs the browser because it compiles a shader.
 *
 * `speed={0}` pins the filter to a single frame. The hero is static, and a
 * looping canvas behind the H1 would both distract and rule out the page's
 * no-JavaScript budget elsewhere. It also means there is no motion to suppress
 * under `prefers-reduced-motion`.
 *
 * The palette is a literal copy of three tokens from `app/(home)/home.css` —
 * `--background`, `--home-accent` and `--foreground` — because shader uniforms
 * are numbers, not CSS custom properties, and cannot read them. If the homepage
 * palette moves, these move with it.
 */
export function HomeHeroDither() {
	return (
		<div className="ss-home-hero-dither" aria-hidden="true">
			<ImageDithering
				image="/homepage/cta-dither-background.webp"
				fit="cover"
				speed={0}
				type="8x8"
				size={3}
				colorSteps={3}
				colorBack="#141414"
				colorFront="#f26a4b"
				colorHighlight="#e8e3da"
				style={{ width: "100%", height: "100%" }}
			/>
		</div>
	);
}
