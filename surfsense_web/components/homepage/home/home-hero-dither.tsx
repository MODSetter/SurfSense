"use client";

import { ImageDithering } from "@paper-design/shaders-react";

/**
 * The hero's dithered backdrop.
 *
 * `ImageDithering` is a WebGL filter: it uploads
 * `public/homepage/cta-dither-background.png` as a texture and re-renders it
 * through a Bayer matrix, so the artwork arrives as a coarse two-tone stipple
 * rather than a photograph. The source must stay same-origin — a cross-origin
 * URL, `next/image`'s `/_next/image?...` included, taints the canvas — which is
 * why it is referenced as a plain path out of `public/`.
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
				image="/homepage/cta-dither-background.png"
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
