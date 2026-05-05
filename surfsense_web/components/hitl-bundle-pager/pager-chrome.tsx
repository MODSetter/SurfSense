"use client";

import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useHitlBundle } from "@/lib/hitl";

/**
 * Prev/next nav and Submit for the current step of an active HITL bundle.
 * Submission is gated on every action_request having a staged decision.
 */
export function PagerChrome() {
	const bundle = useHitlBundle();
	if (!bundle) return null;

	const total = bundle.toolCallIds.length;
	const step = bundle.currentStep;
	const allStaged = bundle.stagedCount === total;

	return (
		<div className="mt-3 flex items-center gap-2 rounded-md border border-border bg-muted/40 p-2 text-sm">
			<Button
				type="button"
				size="sm"
				variant="outline"
				onClick={bundle.prev}
				disabled={step === 0}
				aria-label="Previous approval"
			>
				<ChevronLeftIcon className="h-4 w-4" />
			</Button>
			<span className="font-medium tabular-nums">
				{step + 1} / {total}
			</span>
			<span className="text-muted-foreground">·</span>
			<span className="text-muted-foreground">
				{bundle.stagedCount} of {total} decided
			</span>
			<Button
				type="button"
				size="sm"
				variant="outline"
				onClick={bundle.next}
				disabled={step >= total - 1}
				aria-label="Next approval"
			>
				<ChevronRightIcon className="h-4 w-4" />
			</Button>
			<div className="ml-auto">
				<Button
					type="button"
					size="sm"
					onClick={bundle.submit}
					disabled={!allStaged}
					title={allStaged ? "Submit decisions" : "Decide every action first"}
				>
					Submit decisions
				</Button>
			</div>
		</div>
	);
}
