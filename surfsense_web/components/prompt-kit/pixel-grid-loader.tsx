"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

const DRIVE_DELAYS = Array.from({ length: 9 }, (_, index) => {
	const row = Math.floor(index / 3);
	const column = index % 3;
	return (column + Math.abs(row - 1)) * 90;
});
const DRIVE_CELLS = DRIVE_DELAYS.map((delay, index) => ({
	id: `cell-${Math.floor(index / 3)}-${index % 3}`,
	delay,
}));

export const PixelGridLoader = memo(function PixelGridLoader({
	active = true,
	className,
}: {
	active?: boolean;
	className?: string;
}) {
	return (
		<span
			aria-hidden="true"
			className={cn("grid shrink-0 grid-cols-[repeat(3,4px)] gap-[1.5px]", className)}
		>
			{DRIVE_CELLS.map(({ id, delay }) => (
				<span
					key={id}
					className="size-[4px] rounded-[1px] bg-foreground opacity-15 motion-reduce:animate-none"
					style={{
						animation: active ? `pixel-on 650ms ease-in-out ${delay}ms infinite` : "none",
					}}
				/>
			))}
		</span>
	);
});

export { DRIVE_DELAYS };
