import type { StaticImageData } from "next/image";
import Image from "next/image";
import type { ReactNode } from "react";

/**
 * The section's scene behind a row's mock-up, darkened a little so white glass
 * reads on it. Each row frames a different part of the one picture.
 */
export function ScenePanel({
	scene,
	position = "center",
	children,
}: {
	scene: StaticImageData;
	position?: string;
	children: ReactNode;
}) {
	return (
		<div aria-hidden="true" className="relative min-h-72 overflow-hidden rounded-2xl md:min-h-80">
			<Image
				src={scene}
				alt=""
				fill
				sizes="(max-width: 767px) 100vw, 50vw"
				quality={85}
				placeholder="blur"
				className="object-cover select-none"
				style={{ objectPosition: position }}
			/>
			<div className="absolute inset-0 bg-foreground/50" />
			<div className="absolute inset-0 flex flex-col justify-center">{children}</div>
		</div>
	);
}
