import { cn } from "@/lib/utils";

interface ShortcutKbdProps {
	keys: string[];
	className?: string;
}

export function ShortcutKbd({ keys, className }: ShortcutKbdProps) {
	if (keys.length === 0) return null;

	return (
		<span className={cn("ml-2 inline-flex items-center gap-0.5 text-white/85", className)}>
			{keys.map((key) => (
				<kbd
					key={key}
					className={cn(
						"inline-flex h-[18px] items-center justify-center rounded-[4px] bg-white/[0.18] font-sans text-[11px] leading-none",
						key.length > 1 ? "px-1" : "w-[18px]"
					)}
				>
					{key}
				</kbd>
			))}
		</span>
	);
}
