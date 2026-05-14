"use client";

import type { ReasoningMessagePartComponent } from "@assistant-ui/react";
import { ChevronRightIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Renders the structured `reasoning` part emitted by the backend stream
 * (typed reasoning deltas from the chat model).
 *
 * Behaviour mirrors the existing `ThinkingStepsDisplay`:
 *  - collapsed by default;
 *  - auto-expanded while the part is still `running`;
 *  - auto-collapsed once status flips to `complete`.
 *
 * The component is registered via the `Reasoning` slot on
 * `MessagePrimitive.Parts` in `assistant-message.tsx` so it lives at the
 * exact ordinal position of the reasoning block in the message content
 * array (i.e. above the assistant text that follows it).
 */
export const ReasoningMessagePart: ReasoningMessagePartComponent = ({ text, status }) => {
	const isRunning = status?.type === "running";
	const [isOpen, setIsOpen] = useState(() => isRunning);

	useEffect(() => {
		if (isRunning) {
			setIsOpen(true);
		} else if (status?.type === "complete") {
			setIsOpen(false);
		}
	}, [isRunning, status?.type]);

	const headerLabel = useMemo(() => {
		if (isRunning) return "Thinking";
		if (status?.type === "incomplete") return "Thinking interrupted";
		return "Thought";
	}, [isRunning, status?.type]);

	if (!text || text.length === 0) {
		if (!isRunning) return null;
	}

	return (
		<div className="mx-auto w-full max-w-(--thread-max-width) px-2 py-2">
			<div className="rounded-lg">
				<Button
					variant="ghost"
					type="button"
					onClick={() => setIsOpen((prev) => !prev)}
					className={cn(
						"h-auto w-full justify-start gap-1.5 p-0 text-left text-sm font-normal transition-colors hover:bg-transparent",
						"text-muted-foreground hover:text-accent-foreground"
					)}
				>
					{isRunning ? (
						<TextShimmerLoader text={headerLabel} size="sm" />
					) : (
						<span>{headerLabel}</span>
					)}
					<ChevronRightIcon
						data-icon="inline-end"
						className={cn("transition-transform duration-200", isOpen && "rotate-90")}
					/>
				</Button>

				<div
					className={cn(
						"grid transition-[grid-template-rows] duration-300 ease-out",
						isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
					)}
				>
					<div className="overflow-hidden">
						<div className="mt-2 border-l border-muted-foreground/30 pl-3 text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap wrap-break-word">
							{text}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};
