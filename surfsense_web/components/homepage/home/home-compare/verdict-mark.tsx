import type { CompareVerdict } from "@/components/homepage/home/home-content";
import { Cancel01Icon, CheckIcon, MinusSignIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * A cell's verdict as a small disc. Decorative: the cell's text says the same
 * thing, so the mark is hidden from assistive technology. Every column uses
 * the same marks, so the comparison stays even-handed.
 */
export function VerdictMark({ verdict }: { verdict: CompareVerdict }) {
	return (
		<span
			aria-hidden="true"
			className={cn(
				"grid size-5 shrink-0 place-items-center rounded-full",
				verdict === "yes"
					? "bg-foreground text-background"
					: "bg-(--home-badge) text-muted-foreground"
			)}
		>
			{verdict === "yes" && <CheckIcon className="size-3" />}
			{verdict === "no" && <Cancel01Icon className="size-3" />}
			{verdict === "partial" && <MinusSignIcon className="size-3" />}
		</span>
	);
}
