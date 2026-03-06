import { cn } from "@/lib/utils";

interface ShortcutKbdProps {
	keys: string[];
	className?: string;
}

export function ShortcutKbd({ keys, className }: ShortcutKbdProps) {
	if (keys.length === 0) return null;

	return (
		<span className={cn("ml-2 inline-flex items-center gap-0.5 text-white/50", className)}>
			{keys.map((key) => (
				<kbd
					key={key}
					className="inline-flex size-[16px] items-center justify-center rounded-[3px] bg-white/[0.08] font-sans text-[10px] leading-none"
				>
					{key}
				</kbd>
			))}
		</span>
	);
}
