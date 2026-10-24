import AirGapDioramaSvg from "@/components/homepage/home/home-air-gap/diorama/air-gap-diorama.svg";

/**
 * The machine as an isometric diorama: laptop at the centre, the index and an
 * unplugged router (step 1), the model rack and key card (step 2), the outputs
 * (step 3). SVGR renders it inline so `data-active` on the section can light
 * each step's `data-group`; edit the generator, not the generated SVG.
 */
export function AirGapDiorama() {
	return (
		<div
			aria-hidden="true"
			className="mx-auto w-full select-none lg:mx-0 [&>svg]:block [&>svg]:h-auto [&>svg]:w-full [&>svg]:overflow-visible"
		>
			<AirGapDioramaSvg />
		</div>
	);
}
