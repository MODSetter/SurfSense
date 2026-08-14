import type { LucideIcon } from "lucide-react";
import Image from "next/image";
import type { FC } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { cn } from "@/lib/utils";
import { FadeSwapText } from "../fade-swap-text";
import type { ItemStatus } from "../types";

/**
 * The title row + sub-bullets shared by every timeline item kind. The
 * timeline's chrome (status dot, indent, vertical line) renders to the
 * left; this fills the right column.
 *
 * Status-aware text styling matches the legacy ``StepBody`` semantics:
 *   running   → emphasised (font-medium foreground)
 *   completed → muted
 *   pending   → muted/60
 *   error     → destructive
 *   cancelled → strikethrough muted
 *
 * Sub-bullets render via ``ChainOfThoughtItem`` (reused from
 * ``components/prompt-kit/chain-of-thought``) — same component the
 * legacy ``StepBody`` used.
 */
export const ItemHeader: FC<{
	title: string;
	status: ItemStatus;
	icon?: LucideIcon;
	logo?: { src: string; alt: string };
}> = ({ title, status, icon: Icon, logo }) => (
	<div className="min-w-0">
		<div
			className={cn(
				"flex min-w-0 items-start gap-2 text-sm leading-5",
				status === "running" && "text-foreground font-medium",
				status === "completed" && "text-muted-foreground",
				status === "pending" && "text-muted-foreground/60",
				status === "error" && "text-destructive",
				status === "cancelled" && "text-muted-foreground line-through"
			)}
		>
			{logo ? (
				<Image src={logo.src} alt="" width={16} height={16} className="mt-0.5 size-4 shrink-0" />
			) : Icon ? (
				<Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
			) : null}
			<FadeSwapText
				swapKey={`${status}:${title}`}
				className="min-w-0 flex-1"
				contentClassName={status === "running" ? "truncate" : "wrap-break-word"}
			>
				{status === "running" ? (
					<TextShimmerLoader text={title} size="md" className="truncate" />
				) : (
					title
				)}
			</FadeSwapText>
		</div>
	</div>
);
