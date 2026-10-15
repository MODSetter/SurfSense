import type { ReactNode } from "react";

/**
 * One looping row of chips, on the logo cloud's `.ss-home-marquee`: the run
 * renders twice and slides by half, so the seam never shows, and the
 * reduced-motion rule in `home.css` holds it still.
 */
export function ChipMarquee({
	children,
	seconds,
	reverse = false,
}: {
	children: ReactNode;
	seconds: number;
	reverse?: boolean;
}) {
	return (
		<div className="overflow-hidden">
			<div
				className="ss-home-marquee flex w-max"
				style={{
					animationDuration: `${seconds}s`,
					animationDirection: reverse ? "reverse" : "normal",
				}}
			>
				<div className="flex gap-3 pr-3">{children}</div>
				<div className="flex gap-3 pr-3">{children}</div>
			</div>
		</div>
	);
}
