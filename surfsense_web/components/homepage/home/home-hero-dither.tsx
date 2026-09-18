"use client";

import { getShaderColorFromString, ShaderMount } from "@paper-design/shaders-react";
import { useEffect, useState } from "react";
import { homeHeroDitherFragmentShader } from "./home-hero-dither-shader";

/**
 * The hero's animated, dithered backdrop.
 *
 * A WebGL filter over `public/homepage/cta-dither-background.webp`: the image
 * is uploaded as a texture and re-rendered through a Bayer matrix, so the
 * artwork arrives as a coarse two-tone stipple rather than a photograph, and
 * the stipple moves — the lit wave sways and its grain drifts along the crest.
 * See `home-hero-dither-shader.ts` for how the motion is produced.
 *
 * It is mounted through the library's generic `ShaderMount` with a custom
 * fragment shader because neither stock component does the job: the library's
 * `ImageDithering` has no time uniform, and its animated `Dithering` takes no
 * image. The uniforms below mirror what `ImageDithering` would set, plus
 * `u_flow` for the motion amount.
 *
 * The source must stay same-origin — a cross-origin URL, `next/image`'s
 * `/_next/image?...` included, taints the canvas — which is why it is
 * referenced as a plain path out of `public/`. The texture is 1200px wide, not
 * the source artwork's 1672px. `u_pxSize: 3` quantises the output into 3px
 * cells, so the hero samples roughly 383x200 of them and detail beyond that is
 * discarded before anything is drawn.
 *
 * The only client component on the landing page. Everything around it stays a
 * server component; this one needs the browser because it compiles a shader.
 *
 * Under `prefers-reduced-motion` the speed drops to 0, which stops the frame
 * loop entirely and pins the filter to a single frame — the pattern still
 * draws, it just stops moving.
 *
 * The palette is a literal copy of two tokens from `app/(home)/home.css` —
 * `--background` and `--muted-foreground` — because shader uniforms
 * are numbers, not CSS custom properties, and cannot read them. If the homepage
 * palette moves, these move with it.
 */
export function HomeHeroDither() {
	const reducedMotion = usePrefersReducedMotion();

	return (
		<div className="ss-home-hero-dither" aria-hidden="true">
			<ShaderMount
				fragmentShader={homeHeroDitherFragmentShader}
				speed={reducedMotion ? 0 : 1}
				uniforms={{
					u_image: "/homepage/cta-dither-background.webp",
					u_colorBack: getShaderColorFromString("#141414"),
					u_colorFront: getShaderColorFromString("#8e8a83"),
					// Same as front: the shader swaps to the highlight above ~96%
					// brightness, and the drifting grain pushes crest cells over that
					// line, so a distinct highlight would flash pale pixels. Matching it
					// to the ink gives classic two-colour dithering.
					u_colorHighlight: getShaderColorFromString("#8e8a83"),
					u_type: 4, // 8x8 Bayer
					u_pxSize: 3,
					u_colorSteps: 3,
					u_flow: 1,
					u_fit: 2, // cover
					u_scale: 1,
					u_rotation: 0,
					u_offsetX: 0,
					u_offsetY: 0,
					u_originX: 0.5,
					u_originY: 0.5,
					u_worldWidth: 0,
					u_worldHeight: 0,
				}}
				style={{ width: "100%", height: "100%" }}
			/>
		</div>
	);
}

function usePrefersReducedMotion() {
	const [reduced, setReduced] = useState(false);

	useEffect(() => {
		const query = window.matchMedia("(prefers-reduced-motion: reduce)");
		const update = () => setReduced(query.matches);
		update();
		query.addEventListener("change", update);
		return () => query.removeEventListener("change", update);
	}, []);

	return reduced;
}
