import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A translucent pill for text set on a painted scene. No backdrop blur: the
 * plugins row slides twenty of these, and a moving blur repaints every frame.
 */
export function GlassChip({
	icon,
	label,
	large = false,
}: {
	icon: ReactNode;
	label: string;
	large?: boolean;
}) {
	return (
		<span
			className={cn(
				"flex shrink-0 items-center rounded-full bg-black/25 font-medium whitespace-nowrap text-white",
				large
					? "h-11 gap-2 px-4.5 text-[0.9375rem] [&_svg]:size-[1.125rem]"
					: "h-10 gap-2 px-4 text-sm [&_svg]:size-4"
			)}
		>
			{icon}
			{label}
		</span>
	);
}
