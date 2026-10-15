import Image from "next/image";
import heroScene from "@/components/homepage/home/home-hero-scene.webp";

/**
 * The painted rotunda and sky behind the homepage hero, filling its
 * positioned parent.
 *
 * `next/image` serves AVIF or WebP at the width each screen needs, from the
 * 3296px master, and inlines a tiny blurred preview so the scene shows before
 * the image arrives.
 *
 * `sizes` is the width the scene is drawn at, not the box width: the 1.73:1 image
 * covers its box, so in a tall box it renders 1.73 times the box height wide.
 */
// Grain is an overlay, not baked into the WebP: noise defeats compression, and
// a tiled layer stays sharp when the site scales up on wide monitors.
// Raw turbulence clusters around mid-grey with patchy alpha, which an overlay
// blend all but ignores; the transfer stretches its contrast and makes it opaque.
const GRAIN_SVG = `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/><feComponentTransfer><feFuncR type='linear' slope='3' intercept='-1'/><feFuncG type='linear' slope='3' intercept='-1'/><feFuncB type='linear' slope='3' intercept='-1'/><feFuncA type='linear' slope='0' intercept='1'/></feComponentTransfer></filter><rect width='100%' height='100%' filter='url(#n)'/></svg>`;
const FILM_GRAIN = `url("data:image/svg+xml,${encodeURIComponent(GRAIN_SVG)}")`;

export function HomeScene({ sizes, priority = false }: { sizes: string; priority?: boolean }) {
	return (
		<>
			<Image
				src={heroScene}
				alt=""
				fill
				priority={priority}
				sizes={sizes}
				quality={85}
				placeholder="blur"
				draggable={false}
				className="object-cover object-center select-none"
			/>
			<div
				aria-hidden
				className="pointer-events-none absolute inset-0 opacity-[0.25] mix-blend-overlay"
				style={{ backgroundImage: FILM_GRAIN, backgroundSize: "200px 200px" }}
			/>
		</>
	);
}
